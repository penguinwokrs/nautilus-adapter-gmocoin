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
from nautilus_trader.model.identifiers import Venue, ClientId, AccountId, ClientOrderId, InstrumentId, Symbol, VenueOrderId
from nautilus_trader.model.enums import (
    OrderSide, OrderType, OmsType, AccountType, OrderStatus,
    TimeInForce, LiquiditySide,
)
from nautilus_trader.execution.messages import (
    SubmitOrder, CancelOrder, ModifyOrder,
    GenerateOrderStatusReport, GenerateOrderStatusReports,
    GenerateFillReports, GeneratePositionStatusReports,
)
from nautilus_trader.execution.reports import OrderStatusReport, FillReport, PositionStatusReport
from nautilus_trader.model.identifiers import TradeId, PositionId
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.model.enums import PositionSide

from .config import GmocoinExecClientConfig
from .constants import NAUTILUS_TO_GMO_ORDER_TYPE, ORDER_STATUS_MAP, ORDER_TYPE_MAP, TIME_IN_FORCE_MAP

try:
    from . import _nautilus_gmocoin as gmocoin
except ImportError:
    import _nautilus_gmocoin as gmocoin


class GmocoinExecutionClient(LiveExecutionClient):
    """
    GMO Coin live execution client.
    Wraps Rust GmocoinExecutionClient for REST orders and Private WebSocket.
    """

    _CLIENT_OID_LOOKUP_RETRIES = 10
    _CLIENT_OID_LOOKUP_DELAY_S = 0.1

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
            getattr(self.config, 'rate_limit_per_sec', None),
        )
        self._rust_client.set_order_callback(self._handle_ws_message)

        self._rest_client = gmocoin.GmocoinRestClient(
            self.config.api_key or "",
            self.config.api_secret or "",
            self.config.timeout_ms,
            self.config.proxy_url,
            getattr(self.config, 'rate_limit_per_sec', None),
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

            # Map TimeInForce
            NAUTILUS_TO_GMO_TIF = {
                TimeInForce.GTC: "FAS",
                TimeInForce.IOC: "FAK",
                TimeInForce.FOK: "FOK",
            }
            tif = None
            if hasattr(order, 'time_in_force') and order.time_in_force != TimeInForce.GTC:
                tif = NAUTILUS_TO_GMO_TIF.get(order.time_in_force)

            # Check for post_only -> SOK
            if hasattr(order, 'is_post_only') and order.is_post_only:
                tif = "SOK"

            amount = str(order.quantity)
            client_id = str(order.client_order_id)

            # Extract tags for leverage parameters
            settle_type = None
            losscut_price = None
            if hasattr(order, 'tags') and order.tags:
                for tag in order.tags:
                    tag_str = str(tag)
                    if tag_str.startswith("settleType="):
                        settle_type = tag_str.split("=", 1)[1]
                    elif tag_str.startswith("losscutPrice="):
                        losscut_price = tag_str.split("=", 1)[1]

            resp_json = await self._rust_client.submit_order(
                gmo_symbol, amount, side, order_type, client_id, price, tif, None,
                losscut_price, settle_type,
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

    def modify_order(self, command: ModifyOrder) -> None:
        self.create_task(self._modify_order(command))

    async def _modify_order(self, command: ModifyOrder) -> None:
        try:
            if not command.venue_order_id:
                self._logger.error("ModifyOrder requires venue_order_id")
                return

            venue_order_id_str = str(command.venue_order_id)
            new_price = str(command.price) if command.price else None

            if not new_price:
                self._logger.error("ModifyOrder requires price for GMO Coin changeOrder")
                return

            await self._rust_client.change_order(
                venue_order_id_str,
                new_price,
                None,  # losscutPrice - v0.2
            )

            self.generate_order_updated(
                strategy_id=command.strategy_id,
                instrument_id=command.instrument_id,
                client_order_id=command.client_order_id,
                venue_order_id=command.venue_order_id,
                quantity=command.quantity if command.quantity else None,
                price=command.price,
                trigger_price=command.trigger_price,
                ts_event=self._clock.timestamp_ns(),
            )

        except Exception as e:
            self._logger.error(f"Modify failed: {e}")

    def _handle_ws_message(self, event_type: str, message: str):
        """Handle incoming Private WebSocket message from Rust client."""
        self.log.debug(f"WS Event Received: {event_type}")
        try:
            data = json.loads(message)
            if event_type == "OrderUpdate":
                venue_order_id = VenueOrderId(str(data.get("orderId")))
                self.create_task(self._process_order_update_from_data(venue_order_id, data))
            elif event_type == "ExecutionUpdate":
                self.log.info(f"Received ExecutionUpdate via WS: order_id={data.get('orderId')}, executionId={data.get('executionId')}")
                venue_order_id = VenueOrderId(str(data.get("orderId")))
                self.create_task(self._process_execution_update(venue_order_id, data))
            elif event_type == "AssetUpdate":
                self._process_asset_update(data)
            elif event_type == "PositionUpdate":
                self.log.info(f"Received PositionUpdate via WS: positionId={data.get('positionId')}")
            elif event_type == "PositionSummaryUpdate":
                self.log.info(f"Received PositionSummaryUpdate via WS: symbol={data.get('symbol')}")
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

            total_val = Decimal(data.get("amount", "0"))
            available_val = Decimal(data.get("available", "0"))
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

    async def _lookup_order_with_retry(self, venue_order_id: VenueOrderId) -> Optional[Order]:
        """Lookup order via cache with retries for race condition with order acceptance."""
        client_oid = None
        for _ in range(self._CLIENT_OID_LOOKUP_RETRIES):
            client_oid = self._cache.client_order_id(venue_order_id)
            if client_oid:
                break
            await asyncio.sleep(self._CLIENT_OID_LOOKUP_DELAY_S)

        if not client_oid:
            self.log.warning(f"ClientOrderId not found for venue_order_id: {venue_order_id} after retries")
            return None

        order = self._cache.order(client_oid)
        if not order:
            self.log.warning(f"Order not found in cache for client_order_id: {client_oid}")
            return None

        return order

    def _get_quote_currency(self, instrument_id: InstrumentId):
        """Find instrument and return its quote currency, falling back to JPY."""
        instrument = self._instrument_provider.find(instrument_id)
        if instrument is None and hasattr(self, '_cache'):
            instrument = self._cache.instrument(instrument_id)
        return JPY if not instrument else instrument.quote_currency

    async def _process_execution_update(self, venue_order_id: VenueOrderId, data: dict):
        """Process executionEvents channel WS message with accurate fill data."""
        try:
            execution_id = str(data.get("executionId", ""))
            if not execution_id:
                self.log.warning("ExecutionUpdate missing executionId, skipping")
                return

            order = await self._lookup_order_with_retry(venue_order_id)
            if not order:
                return

            # Initialize order state
            oid_str = str(venue_order_id)
            if oid_str not in self._order_states:
                self._order_states[oid_str] = {
                    "last_executed_qty": Decimal("0"),
                    "reported_trades": set(),
                }

            state = self._order_states[oid_str]

            # Dedup by executionId
            if execution_id in state["reported_trades"]:
                self.log.debug(f"ExecutionUpdate duplicate executionId={execution_id}, skipping")
                return

            # Extract fill data from WS executionEvents fields
            # Use explicit None checks to avoid falsy 0 values being skipped
            exec_price = Decimal(data.get("executionPrice") if data.get("executionPrice") is not None else data.get("price", "0"))
            exec_size = Decimal(data.get("executionSize") if data.get("executionSize") is not None else data.get("size", "0"))
            fee = Decimal(data.get("fee", "0"))

            if exec_size <= 0:
                self.log.warning(f"ExecutionUpdate with zero size, executionId={execution_id}")
                return

            quote_currency = self._get_quote_currency(order.instrument_id)
            commission = Money(fee, quote_currency)

            self.generate_order_filled(
                strategy_id=order.strategy_id,
                instrument_id=order.instrument_id,
                client_order_id=order.client_order_id,
                venue_order_id=venue_order_id,
                venue_position_id=None,
                trade_id=TradeId(execution_id),
                order_side=order.side,
                order_type=order.order_type,
                last_qty=exec_size,
                last_px=exec_price,
                quote_currency=quote_currency,
                liquidity_side=self._infer_liquidity_side(order),
                commission=commission,
                ts_event=self._clock.timestamp_ns(),
            )

            # Mark as reported AFTER successful fill generation to avoid
            # permanently losing fills if generate_order_filled raises
            state["reported_trades"].add(execution_id)
            state["last_executed_qty"] += exec_size

            self.log.info(
                f"ExecutionUpdate fill: executionId={execution_id}, "
                f"price={exec_price}, size={exec_size}, fee={fee}"
            )

        except Exception as e:
            self.log.error(f"Failed to process ExecutionUpdate: {e}", exc_info=True)

    def _infer_liquidity_side(self, order: Order) -> LiquiditySide:
        """Infer liquidity side from order type."""
        if order.order_type == OrderType.MARKET:
            return LiquiditySide.TAKER
        if hasattr(order, 'is_post_only') and order.is_post_only:
            return LiquiditySide.MAKER
        if order.order_type == OrderType.LIMIT:
            return LiquiditySide.MAKER
        return LiquiditySide.NO_LIQUIDITY_SIDE

    async def _process_order_update_from_data(self, venue_order_id: VenueOrderId, data: dict):
        order = await self._lookup_order_with_retry(venue_order_id)
        if not order:
            return

        quote_currency = self._get_quote_currency(order.instrument_id)

        await self._process_order_update(order, venue_order_id, quote_currency, data)

    async def _process_order_update(self, order: Order, venue_order_id: VenueOrderId, quote_currency, data: dict) -> bool:
        try:
            status = data.get("orderStatus") if data.get("orderStatus") is not None else data.get("status")
            executed_qty = Decimal(data.get("orderExecutedSize") if data.get("orderExecutedSize") is not None else data.get("executedSize", "0"))

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
                avg_price = Decimal(data.get("orderPrice") if data.get("orderPrice") is not None else data.get("price", "0"))
                commission = Money(Decimal("0"), quote_currency)

                # Try to get detailed execution info
                new_execs = []
                try:
                    history_json = await self._rust_client.get_executions(str(venue_order_id))
                    history = json.loads(history_json)
                    raw_executions = history.get("list", [])

                    for ex in raw_executions:
                        eid = str(ex.get("executionId"))
                        if eid not in state["reported_trades"]:
                            new_execs.append(ex)

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
                    trade_id=None,
                    order_side=order.side,
                    order_type=order.order_type,
                    last_qty=delta,
                    last_px=avg_price,
                    quote_currency=quote_currency,
                    liquidity_side=self._infer_liquidity_side(order),
                    commission=commission,
                    ts_event=self._clock.timestamp_ns(),
                )

                # Mark as reported AFTER successful fill generation to avoid
                # permanently losing fills if generate_order_filled raises
                for ex in new_execs:
                    state["reported_trades"].add(str(ex.get("executionId")))

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
                self._order_states.pop(oid_str, None)
                return True

            if status == "EXECUTED":
                self._order_states.pop(oid_str, None)
                return True

        except Exception as e:
            self._logger.error(f"Update processing failed: {e}")

        return False

    # Required abstract methods

    GMO_ORDER_STATUS_MAP = {
        "WAITING": OrderStatus.ACCEPTED,
        "ORDERED": OrderStatus.ACCEPTED,
        "MODIFYING": OrderStatus.ACCEPTED,
        "CANCELLING": OrderStatus.PENDING_CANCEL,
        "CANCELED": OrderStatus.CANCELED,
        "EXECUTED": OrderStatus.FILLED,
        "EXPIRED": OrderStatus.EXPIRED,
    }
    GMO_ORDER_TYPE_MAP = {
        "MARKET": OrderType.MARKET,
        "LIMIT": OrderType.LIMIT,
        "STOP": OrderType.STOP_MARKET,
    }
    GMO_TIF_MAP = {
        "FAK": TimeInForce.IOC,
        "FAS": TimeInForce.GTC,
        "FOK": TimeInForce.FOK,
        "SOK": TimeInForce.GTC,
    }

    def _parse_order_status_report(
        self,
        order_data: dict,
        instrument_id: InstrumentId | None = None,
        client_order_id: ClientOrderId | None = None,
    ) -> OrderStatusReport:
        if client_order_id is None:
            coid_str = order_data.get("clientOrderId")
            if coid_str:
                client_order_id = ClientOrderId(coid_str)

        venue_oid = VenueOrderId(str(order_data.get("orderId")))
        side_str = order_data.get("side", "BUY")
        order_side = OrderSide.BUY if side_str == "BUY" else OrderSide.SELL

        exec_type = order_data.get("executionType", "LIMIT")
        order_type = self.GMO_ORDER_TYPE_MAP.get(exec_type, OrderType.LIMIT)

        tif_str = order_data.get("timeInForce", "FAS")
        time_in_force = self.GMO_TIF_MAP.get(tif_str, TimeInForce.GTC)

        status_str = order_data.get("status", "ORDERED")
        order_status = self.GMO_ORDER_STATUS_MAP.get(status_str, OrderStatus.ACCEPTED)

        size = Decimal(order_data.get("size", "0"))
        executed_size = Decimal(order_data.get("executedSize", "0"))

        price_str = order_data.get("price")
        price = Price(Decimal(price_str), precision=0) if price_str else None

        if instrument_id is None:
            symbol = order_data.get("symbol", "BTC")
            instrument_id = InstrumentId(Symbol(f"{symbol}/JPY"), self.venue)

        ts_now = self._clock.timestamp_ns()

        return OrderStatusReport(
            account_id=self._account_id,
            instrument_id=instrument_id,
            venue_order_id=venue_oid,
            order_side=order_side,
            order_type=order_type,
            time_in_force=time_in_force,
            order_status=order_status,
            quantity=Quantity(size, precision=8),
            filled_qty=Quantity(executed_size, precision=8),
            report_id=UUID4(),
            ts_accepted=ts_now,
            ts_last=ts_now,
            ts_init=ts_now,
            client_order_id=client_order_id,
            price=price,
        )

    async def generate_order_status_report(
        self,
        command: GenerateOrderStatusReport,
    ) -> OrderStatusReport | None:
        try:
            venue_order_id = command.venue_order_id
            if venue_order_id is None and command.client_order_id is not None:
                venue_order_id = self._cache.venue_order_id(command.client_order_id)
            if venue_order_id is None:
                self._logger.warning("generate_order_status_report: no venue_order_id available")
                return None

            resp_json = await self._rust_client.get_order(str(venue_order_id))
            resp = json.loads(resp_json)
            orders_list = resp if isinstance(resp, list) else resp.get("list", [])

            if not orders_list:
                self._logger.warning(f"generate_order_status_report: no order found for {venue_order_id}")
                return None

            return self._parse_order_status_report(
                orders_list[0],
                instrument_id=command.instrument_id,
                client_order_id=command.client_order_id,
            )
        except Exception as e:
            self._logger.error(f"Failed to generate order status report: {e}")
            return None

    async def generate_order_status_reports(self, command: GenerateOrderStatusReports) -> list[OrderStatusReport]:
        reports = []
        try:
            instrument_id = command.instrument_id
            # Determine which symbols to query
            symbols = set()
            if instrument_id:
                symbols.add(instrument_id.symbol.value.split("/")[0])
            else:
                for inst in self._instrument_provider.get_all().values() if hasattr(self._instrument_provider.get_all, 'values') else self._instrument_provider.get_all():
                    symbols.add(inst.id.symbol.value.split("/")[0])

            if not symbols:
                symbols.add("BTC")

            for symbol in symbols:
                try:
                    resp_json = await self._rust_client.get_active_orders(symbol)
                    resp = json.loads(resp_json)
                    orders_list = resp if isinstance(resp, list) else resp.get("list", [])

                    inst_id = InstrumentId(Symbol(f"{symbol}/JPY"), self.venue)

                    for order_data in orders_list:
                        try:
                            report = self._parse_order_status_report(order_data, instrument_id=inst_id)
                            reports.append(report)
                        except Exception as e:
                            self._logger.warning(f"Failed to parse order report: {e}")
                            continue
                except Exception as e:
                    self._logger.warning(f"Failed to fetch active orders for {symbol}: {e}")
                    continue

        except Exception as e:
            self._logger.error(f"Failed to generate order status reports: {e}")

        return reports

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

                    total = Decimal(asset.get("amount", "0"))
                    available = Decimal(asset.get("available", "0"))
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

    async def generate_fill_reports(self, command: GenerateFillReports) -> list[FillReport]:
        reports = []
        try:
            instrument_id = command.instrument_id
            venue_order_id = command.venue_order_id

            # When venue_order_id is specified, fetch only that order's executions
            if venue_order_id:
                try:
                    resp_json = await self._rust_client.get_executions(str(venue_order_id))
                    resp = json.loads(resp_json)
                    exec_list = resp if isinstance(resp, list) else resp.get("list", [])
                    self._parse_fill_reports(exec_list, instrument_id, reports)
                except Exception as e:
                    self._logger.warning(f"Failed to fetch executions for order {venue_order_id}: {e}")
                return reports

            symbols = set()
            if instrument_id:
                symbols.add(instrument_id.symbol.value.split("/")[0])
            else:
                for inst in self._instrument_provider.get_all().values() if hasattr(self._instrument_provider.get_all, 'values') else self._instrument_provider.get_all():
                    symbols.add(inst.id.symbol.value.split("/")[0])

            if not symbols:
                symbols.add("BTC")

            for symbol in symbols:
                try:
                    resp_json = await self._rust_client.get_latest_executions(symbol)
                    resp = json.loads(resp_json)
                    exec_list = resp if isinstance(resp, list) else resp.get("list", [])
                    self._parse_fill_reports(exec_list, instrument_id, reports)
                except Exception as e:
                    self._logger.warning(f"Failed to fetch executions for {symbol}: {e}")
                    continue

        except Exception as e:
            self._logger.error(f"Failed to generate fill reports: {e}")

        return reports

    def _parse_fill_reports(self, exec_list: list, instrument_id, reports: list):
        from nautilus_trader.model.identifiers import InstrumentId, Symbol
        for exec_data in exec_list:
            try:
                venue_oid = VenueOrderId(str(exec_data.get("orderId")))
                trade_id = TradeId(str(exec_data.get("executionId")))
                side_str = exec_data.get("side", "BUY")
                order_side = OrderSide.BUY if side_str == "BUY" else OrderSide.SELL

                exec_size = Decimal(exec_data.get("size", "0"))
                exec_price = Decimal(exec_data.get("price", "0"))
                fee = Decimal(exec_data.get("fee", "0"))

                symbol = exec_data.get("symbol", "BTC")
                inst_id = instrument_id or InstrumentId(Symbol(f"{symbol}/JPY"), Venue("GMOCOIN"))

                instrument = self._instrument_provider.find(inst_id)
                quote_currency = JPY
                if instrument:
                    quote_currency = instrument.quote_currency

                ts_now = self._clock.timestamp_ns()

                report = FillReport(
                    account_id=self._account_id,
                    instrument_id=inst_id,
                    venue_order_id=venue_oid,
                    trade_id=trade_id,
                    order_side=order_side,
                    last_qty=Quantity(exec_size, precision=8),
                    last_px=Price(exec_price, precision=0),
                    commission=Money(fee, quote_currency),
                    liquidity_side=LiquiditySide.NO_LIQUIDITY_SIDE,
                    report_id=UUID4(),
                    ts_event=ts_now,
                    ts_init=ts_now,
                )
                reports.append(report)
            except Exception as e:
                self._logger.warning(f"Failed to parse fill report: {e}")
                continue

    async def generate_position_status_reports(self, command: GeneratePositionStatusReports) -> list[PositionStatusReport]:
        reports = []
        try:
            instrument_id = command.instrument_id
            symbols = set()
            if instrument_id:
                symbols.add(instrument_id.symbol.value.split("/")[0])
            else:
                for inst in self._instrument_provider.get_all().values() if hasattr(self._instrument_provider.get_all, 'values') else self._instrument_provider.get_all():
                    symbols.add(inst.id.symbol.value.split("/")[0])

            if not symbols:
                return reports

            for symbol in symbols:
                try:
                    resp_json = await self._rust_client.get_open_positions(symbol)
                    resp = json.loads(resp_json)
                    pos_list = resp if isinstance(resp, list) else resp.get("list", [])

                    for pos_data in pos_list:
                        try:
                            position_id = PositionId(str(pos_data.get("positionId")))
                            side_str = pos_data.get("side", "BUY")
                            position_side = PositionSide.LONG if side_str == "BUY" else PositionSide.SHORT

                            size = Decimal(pos_data.get("size", "0"))
                            avg_price = Decimal(pos_data.get("price", "0"))

                            from nautilus_trader.model.identifiers import InstrumentId, Symbol
                            inst_id = InstrumentId(Symbol(f"{symbol}/JPY"), Venue("GMOCOIN"))

                            ts_now = self._clock.timestamp_ns()

                            report = PositionStatusReport(
                                account_id=self._account_id,
                                instrument_id=inst_id,
                                position_side=position_side,
                                quantity=Quantity(size, precision=8),
                                report_id=UUID4(),
                                ts_last=ts_now,
                                ts_init=ts_now,
                            )
                            reports.append(report)
                        except Exception as e:
                            self._logger.warning(f"Failed to parse position report: {e}")
                            continue
                except Exception as e:
                    self._logger.warning(f"Failed to fetch positions for {symbol}: {e}")
                    continue

        except Exception as e:
            self._logger.error(f"Failed to generate position status reports: {e}")

        return reports

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
