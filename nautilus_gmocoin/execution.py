import asyncio
import json
import logging
from typing import Dict, List, Optional
from decimal import Decimal

from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.model.orders import Order
from nautilus_trader.model.objects import Money, Currency, AccountBalance
from nautilus_trader.model.events import AccountState
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.model.currencies import JPY
from nautilus_trader.model.identifiers import Venue, ClientId, AccountId, VenueOrderId
from nautilus_trader.model.enums import OrderSide, OrderType, OmsType, AccountType, OrderStatus
from nautilus_trader.execution.messages import SubmitOrder, CancelOrder

from .config import GmocoinExecClientConfig
from .constants import NAUTILUS_TO_GMO_ORDER_TYPE

try:
    from . import _nautilus_gmocoin as gmocoin
except ImportError:
    import _nautilus_gmocoin as gmocoin


class GmocoinExecutionClient(LiveExecutionClient):
    """
    GMO Coin live execution client.
    Wraps Rust GmocoinExecutionClient for REST orders and Private WebSocket.
    """

    def __init__(self, loop, config: GmocoinExecClientConfig, msgbus, cache, clock, instrument_provider: InstrumentProvider):
        super().__init__(
            loop=loop,
            client_id=ClientId("GMOCOIN"),
            venue=Venue("GMOCOIN"),
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            base_currency=None,  # Multi-currency
            instrument_provider=instrument_provider,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            config=config,
        )
        self.config = config
        self._instrument_provider = instrument_provider
        self._logger = logging.getLogger(__name__)
        self._account_id = AccountId("GMOCOIN-001")
        self._set_account_id(self._account_id)
        self._order_states = {}

        self._rust_client = gmocoin.GmocoinExecutionClient(
            self.config.api_key or "",
            self.config.api_secret or "",
            self.config.timeout_ms,
            self.config.proxy_url,
        )
        self._rust_client.set_order_callback(self._handle_ws_message)

        self._rest_client = gmocoin.GmocoinRestClient(
            self.config.api_key or "",
            self.config.api_secret or "",
            self.config.timeout_ms,
            self.config.proxy_url,
        )
        self.log = logging.getLogger("nautilus.gmocoin.execution")

    @property
    def account_id(self) -> AccountId:
        return self._account_id

    async def _connect(self):
        # Register all currencies
        await self._register_all_currencies()

        try:
            # Connect Rust client (Private WebSocket)
            await self._rust_client.connect()
            self.log.info("Private WebSocket started via Rust client")

            # Initial account state
            try:
                reports = await self.generate_account_status_reports()
                if reports:
                    for report in reports:
                        self._send_account_state(report)
                    self.log.info(f"Published {len(reports)} account reports")
            except Exception as e:
                self.log.error(f"Failed to fetch initial account state: {e}")

        except Exception as e:
            self.log.error(f"Failed to connect: {e}")

    async def _disconnect(self):
        self.log.info("GmocoinExecutionClient disconnected")

    def submit_order(self, command: SubmitOrder) -> None:
        self.create_task(self._submit_order(command))

    async def _submit_order(self, command: SubmitOrder) -> None:
        try:
            order = command.order
            instrument_id = order.instrument_id
            # "BTC/JPY" -> "BTC" for GMO Coin
            gmo_symbol = instrument_id.symbol.value.split("/")[0]

            side = "BUY" if order.side == OrderSide.BUY else "SELL"

            order_type = "MARKET"
            price = None
            if order.order_type == OrderType.LIMIT:
                order_type = "LIMIT"
                price = str(order.price)
            elif order.order_type == OrderType.STOP_MARKET:
                order_type = "STOP"
                price = str(order.trigger_price) if hasattr(order, 'trigger_price') else None
            elif order.order_type != OrderType.MARKET:
                return  # Unsupported

            amount = str(order.quantity)
            client_id = str(order.client_order_id)

            resp_json = await self._rust_client.submit_order(
                gmo_symbol, amount, side, order_type, client_id, price
            )

            resp = json.loads(resp_json)
            venue_order_id = VenueOrderId(str(resp.get("order_id")))

            self.generate_order_accepted(
                strategy_id=order.strategy_id,
                instrument_id=order.instrument_id,
                client_order_id=order.client_order_id,
                venue_order_id=venue_order_id,
                ts_event=self._clock.timestamp_ns(),
            )

        except Exception as e:
            self._logger.error(f"Submit failed: {e}")

    def cancel_order(self, command: CancelOrder) -> None:
        self.create_task(self._cancel_order(command))

    async def _cancel_order(self, command: CancelOrder) -> None:
        try:
            if not command.venue_order_id:
                return

            instrument_id = command.instrument_id
            gmo_symbol = instrument_id.symbol.value.split("/")[0]

            await self._rust_client.cancel_order(
                gmo_symbol,
                str(command.venue_order_id),
            )

            self.generate_order_canceled(
                strategy_id=command.strategy_id,
                instrument_id=command.instrument_id,
                client_order_id=command.client_order_id,
                venue_order_id=command.venue_order_id,
                ts_event=self._clock.timestamp_ns(),
            )

        except Exception as e:
            self._logger.error(f"Cancel failed: {e}")

    def _handle_ws_message(self, event_type: str, message: str):
        """Handle incoming Private WebSocket message from Rust client."""
        self.log.debug(f"WS Event Received: {event_type}")
        try:
            data = json.loads(message)
            if event_type == "OrderUpdate":
                venue_order_id = VenueOrderId(str(data.get("orderId")))
                self.create_task(self._process_order_update_from_data(venue_order_id, data))
            elif event_type == "ExecutionUpdate":
                self.log.info(f"Received ExecutionUpdate via WS: order_id={data.get('orderId')}")
                venue_order_id = VenueOrderId(str(data.get("orderId")))
                self.create_task(self._process_order_update_from_data(venue_order_id, data))
            elif event_type == "AssetUpdate":
                self._process_asset_update(data)
            else:
                self.log.debug(f"Unknown WS Event: {event_type}")
        except Exception as e:
            self.log.error(f"Error handling WS message: {e}")

    def _process_asset_update(self, data: dict):
        try:
            asset_code = data.get("symbol", "").upper()
            if not asset_code:
                return

            currency = None
            if hasattr(self._instrument_provider, 'currency'):
                currency = self._instrument_provider.currency(asset_code)

            if currency is None:
                from nautilus_trader.model import currencies
                currency = getattr(currencies, asset_code, None)

            if currency is None:
                self.log.debug(f"Skipping unknown currency: {asset_code}")
                return

            total_val = int(Decimal(data.get("amount", "0")))
            available_val = int(Decimal(data.get("available", "0")))
            locked_val = total_val - available_val

            balance = AccountBalance(
                Money(total_val, currency),
                Money(locked_val, currency),
                Money(available_val, currency),
            )

            import time
            ts_now = int(time.time() * 1_000_000_000)

            account_state = AccountState(
                self._account_id,
                AccountType.CASH,
                None,
                True,
                [balance],
                [],
                {},
                UUID4(),
                ts_now,
                ts_now,
            )
            self._send_account_state(account_state)
            self.log.info(f"Updated account state for {asset_code} via WS")
        except Exception as e:
            self.log.error(f"Failed to process asset update: {e}")

    async def _process_order_update_from_data(self, venue_order_id: VenueOrderId, data: dict):
        # Retry loop for ClientOrderId lookup (race condition)
        client_oid = None
        for _ in range(10):
            client_oid = self._cache.client_order_id(venue_order_id)
            if client_oid:
                break
            await asyncio.sleep(0.1)

        if not client_oid:
            self._logger.warning(
                f"ClientOrderId not found for venue_order_id: {venue_order_id} after retries."
            )
            return

        order = self._cache.order(client_oid)
        if not order:
            self._logger.warning(f"Order not found in cache for client_order_id: {client_oid}")
            return

        instrument = self._instrument_provider.find(order.instrument_id)
        if instrument is None and hasattr(self, '_cache'):
            instrument = self._cache.instrument(order.instrument_id)

        quote_currency = JPY if not instrument else instrument.quote_currency

        await self._process_order_update(order, venue_order_id, quote_currency, data)

    async def _process_order_update(self, order: Order, venue_order_id: VenueOrderId, quote_currency, data: dict) -> bool:
        try:
            status = data.get("status")
            executed_qty = Decimal(data.get("executedSize", "0"))

            # Track fill state
            oid_str = str(venue_order_id)
            if oid_str not in self._order_states:
                self._order_states[oid_str] = {
                    "last_executed_qty": Decimal("0"),
                    "reported_trades": set(),
                }

            state = self._order_states[oid_str]
            last_qty = state["last_executed_qty"]

            # Handle fills
            if executed_qty > last_qty:
                delta = executed_qty - last_qty
                avg_price = Decimal(data.get("price", "0") or "0")
                commission = Money(Decimal("0"), quote_currency)

                # Try to get detailed execution info
                try:
                    history_json = await self._rust_client.get_executions(str(venue_order_id))
                    history = json.loads(history_json)
                    raw_executions = history.get("list", [])

                    new_execs = []
                    for ex in raw_executions:
                        eid = str(ex.get("executionId"))
                        if eid not in state["reported_trades"]:
                            new_execs.append(ex)
                            state["reported_trades"].add(eid)

                    if new_execs:
                        total_fee = Decimal("0")
                        weighted_price_sum = Decimal("0")
                        total_exec_qty = Decimal("0")

                        for ex in new_execs:
                            qty = Decimal(ex.get("size", "0"))
                            px = Decimal(ex.get("price", "0"))
                            fee = Decimal(ex.get("fee", "0"))
                            weighted_price_sum += qty * px
                            total_exec_qty += qty
                            total_fee += fee

                        commission = Money(total_fee, quote_currency)
                        if total_exec_qty > 0:
                            avg_price = weighted_price_sum / total_exec_qty

                except Exception as e:
                    self._logger.warning(f"Failed to fetch execution details: {e}")

                self.generate_order_filled(
                    strategy_id=order.strategy_id,
                    instrument_id=order.instrument_id,
                    client_order_id=order.client_order_id,
                    venue_order_id=venue_order_id,
                    venue_position_id=None,
                    fill_id=None,
                    last_qty=delta,
                    last_px=avg_price,
                    liquidity=None,
                    commission=commission,
                    ts_event=self._clock.timestamp_ns(),
                )

                state["last_executed_qty"] = executed_qty

            # Handle cancel
            if status in ("CANCELED",):
                if order.status not in (OrderStatus.CANCELED, OrderStatus.FILLED, OrderStatus.EXPIRED):
                    self.generate_order_canceled(
                        strategy_id=order.strategy_id,
                        instrument_id=order.instrument_id,
                        client_order_id=order.client_order_id,
                        venue_order_id=venue_order_id,
                        ts_event=self._clock.timestamp_ns(),
                    )
                return True

            if status == "EXECUTED":
                return True

        except Exception as e:
            self._logger.error(f"Update processing failed: {e}")

        return False

    # Required abstract methods

    async def generate_order_status_reports(self, instrument_id=None, client_order_id=None):
        return []

    async def generate_account_status_reports(self, instrument_id=None, client_order_id=None):
        try:
            reports = []
            assets_json = await self._rust_client.get_assets_py()
            self.log.debug(f"Fetched assets: {assets_json[:200]}...")

            assets_data = json.loads(assets_json)
            if isinstance(assets_data, dict):
                assets_data = assets_data.get("data", assets_data)
            if not isinstance(assets_data, list):
                assets_data = []

            nautilus_balances = []
            for asset in assets_data:
                currency_str = asset.get("symbol", "").upper()
                try:
                    currency = None
                    if hasattr(self._instrument_provider, 'currency'):
                        currency = self._instrument_provider.currency(currency_str)
                    if currency is None:
                        from nautilus_trader.model import currencies
                        currency = getattr(currencies, currency_str, None)

                    if currency is None:
                        continue

                    total = int(Decimal(asset.get("amount", "0")))
                    available = int(Decimal(asset.get("available", "0")))
                    locked = total - available

                    nautilus_balances.append(
                        AccountBalance(
                            Money(total, currency),
                            Money(locked, currency),
                            Money(available, currency),
                        )
                    )
                except Exception as e:
                    self._logger.error(f"Failed to parse balance for {currency_str}: {e}")
                    continue

            if not nautilus_balances:
                self.log.warning("No balances found, adding zero JPY balance")
                nautilus_balances.append(
                    AccountBalance(
                        Money(0, JPY),
                        Money(0, JPY),
                        Money(0, JPY),
                    )
                )

            account_state = AccountState(
                self._account_id,
                self.account_type,
                None,
                True,
                nautilus_balances,
                [],
                {},
                UUID4(),
                self._clock.timestamp_ns(),
                self._clock.timestamp_ns(),
            )
            reports.append(account_state)
            return reports

        except Exception as e:
            self._logger.error(f"Failed to generate account status reports: {e}", exc_info=True)
            return []

    async def generate_fill_reports(self, instrument_id=None, client_order_id=None):
        return []

    async def generate_position_status_reports(self, instrument_id=None):
        return []

    async def _register_all_currencies(self):
        """Dynamically register all GMO Coin currencies to the InstrumentProvider."""
        from nautilus_trader.model.currencies import Currency
        try:
            from nautilus_trader.model.enums import CurrencyType
        except ImportError:
            CurrencyType = None

        try:
            symbols_json = await self._rest_client.get_symbols_py()
            data = json.loads(symbols_json)
            if isinstance(data, dict):
                symbols = data.get("data", [])
            elif isinstance(data, list):
                symbols = data
            else:
                return

            codes = set()
            for s in symbols:
                symbol_name = s.get("symbol", "")
                if "_" in symbol_name:
                    parts = symbol_name.split("_")
                    codes.add(parts[0].upper())
                    codes.add(parts[1].upper())
                else:
                    codes.add(symbol_name.upper())
            codes.add("JPY")

            from nautilus_trader.model import currencies as model_currencies
            added_count = 0

            for code in codes:
                if hasattr(self._instrument_provider, "currency"):
                    if self._instrument_provider.currency(code):
                        continue

                if getattr(model_currencies, code, None):
                    continue

                try:
                    ctype = CurrencyType.CRYPTO
                    if code in ("JPY", "USD", "EUR"):
                        ctype = CurrencyType.FIAT

                    currency = Currency(code, 8, 0, code, ctype)

                    if hasattr(self._instrument_provider, "add_currency"):
                        self._instrument_provider.add_currency(currency)
                        added_count += 1
                except Exception as e:
                    self.log.warning(f"Could not add currency {code}: {e}")

            if added_count > 0:
                self.log.info(f"Dynamically registered {added_count} currencies from GMO Coin")

        except Exception as e:
            self.log.error(f"Failed to register currencies: {e}")
