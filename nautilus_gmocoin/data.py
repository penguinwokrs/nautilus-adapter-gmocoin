import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Set

from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.identifiers import ClientId, Venue
from .config import GmocoinDataClientConfig
from .constants import BAR_SPEC_TO_GMO_INTERVAL, BAR_POLL_INTERVALS

try:
    from . import _nautilus_gmocoin as gmocoin
except ImportError:
    import _nautilus_gmocoin as gmocoin


class GmocoinDataClient(LiveMarketDataClient):
    """
    GMO Coin live market data client.
    Actual low-level logic resides in Rust (GmocoinDataClient + GmocoinRestClient).
    """

    def __init__(self, loop, config: GmocoinDataClientConfig, msgbus, cache, clock, instrument_provider=None):
        if instrument_provider is None:
            from nautilus_trader.common.providers import InstrumentProvider
            instrument_provider = InstrumentProvider()

        super().__init__(
            loop=loop,
            client_id=ClientId("GMOCOIN-DATA"),
            venue=Venue("GMOCOIN"),
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=instrument_provider,
            config=config,
        )
        self.config = config
        self._logger = logging.getLogger(__name__)
        self._subscribed_instruments = {}  # "BTC" -> Instrument
        self._bar_poll_tasks: Dict[str, asyncio.Task] = {}  # bar_type_str -> Task
        self._bar_last_timestamps: Dict[str, str] = {}  # bar_type_str -> last openTime

        # Rust clients
        self._rust_client = gmocoin.GmocoinDataClient(
            getattr(self.config, 'ws_rate_limit_per_sec', None),
        )
        self._rust_client.set_data_callback(self._handle_rust_data)

        self._rest_client = gmocoin.GmocoinRestClient(
            self.config.api_key or "",
            self.config.api_secret or "",
            self.config.timeout_ms,
            self.config.proxy_url,
            getattr(self.config, 'rate_limit_per_sec', None),
        )

    async def _connect(self):
        self._logger.info("GmocoinDataClient connecting")

        # Load instruments
        await self._load_instruments()

        # Connect Rust DataClient (Public WebSocket)
        await self._rust_client.connect()
        self._logger.info("Connected to GMO Coin via Rust client (Public WebSocket)")

    async def _disconnect(self):
        for task in self._bar_poll_tasks.values():
            if not task.done():
                task.cancel()
        self._bar_poll_tasks.clear()
        self._bar_last_timestamps.clear()
        await self._rust_client.disconnect()

    async def subscribe(self, instruments: List[Instrument]):
        for instrument in instruments:
            symbol = instrument.id.symbol
            # "BTC/JPY" -> "BTC"
            gmo_symbol = symbol.value.split("/")[0]
            self._subscribed_instruments[gmo_symbol] = instrument

            # Subscribe to all channels for this symbol
            await self._rust_client.subscribe("ticker", gmo_symbol)
            trades_option = "TAKER_ONLY" if self.config.trades_taker_only else None
            await self._rust_client.subscribe("trades", gmo_symbol, trades_option)
            await self._rust_client.subscribe("orderbooks", gmo_symbol)

        self._logger.info(f"Subscribed to {len(instruments)} instruments")

    async def unsubscribe(self, instruments: List[Instrument]):
        pass

    def _handle_rust_data(self, channel: str, data):
        """
        Callback from Rust. channel is "ticker", "orderbooks", or "trades".
        data is a PyObject (Ticker, OrderBook, or Trade).
        """
        try:
            if channel == "ticker":
                self._handle_ticker(data)
            elif channel == "orderbooks":
                self._handle_orderbook(data)
            elif channel == "trades":
                self._handle_trade(data)
        except Exception as e:
            self._logger.error(f"Error handling data from Rust: {e}")

    def _handle_ticker(self, data):
        symbol = data.symbol
        instrument = self._subscribed_instruments.get(symbol)
        if not instrument:
            return

        from nautilus_trader.model.data import QuoteTick
        from nautilus_trader.model.objects import Price, Quantity

        bid = data.bid
        ask = data.ask

        if bid and ask:
            precision = instrument.price_precision
            quote = QuoteTick(
                instrument_id=instrument.id,
                bid_price=Price(float(bid), precision),
                ask_price=Price(float(ask), precision),
                bid_size=Quantity.from_str("0"),
                ask_size=Quantity.from_str("0"),
                ts_event=self._clock.timestamp_ns(),
                ts_init=self._clock.timestamp_ns(),
            )
            self._handle_data(quote)

    def _handle_trade(self, data):
        symbol = data.symbol if data.symbol else None
        if not symbol:
            return
        instrument = self._subscribed_instruments.get(symbol)
        if not instrument:
            return

        from nautilus_trader.model.data import TradeTick
        from nautilus_trader.model.objects import Price, Quantity
        from nautilus_trader.model.enums import AggressorSide
        from nautilus_trader.model.identifiers import TradeId

        side_str = data.side
        aggressor_side = AggressorSide.BUYER if side_str == "BUY" else AggressorSide.SELLER

        tick = TradeTick(
            instrument_id=instrument.id,
            price=Price.from_str(str(data.price)),
            size=Quantity.from_str(str(data.size)),
            aggressor_side=aggressor_side,
            trade_id=TradeId(str(data.timestamp)),
            ts_event=self._clock.timestamp_ns(),
            ts_init=self._clock.timestamp_ns(),
        )
        self._handle_data(tick)

    def _handle_orderbook(self, data):
        # data is an OrderBook pyclass from Rust
        symbol = data.symbol
        instrument = self._subscribed_instruments.get(symbol)
        if not instrument:
            return

        from nautilus_trader.model.data import OrderBookDelta, OrderBookDeltas, BookOrder
        from nautilus_trader.model.enums import BookAction, OrderSide
        from nautilus_trader.model.objects import Price, Quantity

        top_asks, top_bids = data.get_top_n(self.config.order_book_depth)
        ts_init = self._clock.timestamp_ns()

        deltas = []
        deltas.append(OrderBookDelta.clear(instrument.id, 0, ts_init, ts_init))

        for p, q in top_asks:
            order = BookOrder(OrderSide.SELL, Price.from_str(str(p)), Quantity.from_str(str(q)), 0)
            deltas.append(OrderBookDelta(instrument.id, BookAction.ADD, order, 0, 0, ts_init, ts_init))

        for p, q in top_bids:
            order = BookOrder(OrderSide.BUY, Price.from_str(str(p)), Quantity.from_str(str(q)), 0)
            deltas.append(OrderBookDelta(instrument.id, BookAction.ADD, order, 0, 0, ts_init, ts_init))

        snapshot = OrderBookDeltas(instrument.id, deltas)
        self._handle_data(snapshot)

    async def fetch_instruments(self) -> List[Instrument]:
        from nautilus_trader.model.instruments import CurrencyPair
        from nautilus_trader.model.identifiers import InstrumentId, Symbol
        from nautilus_trader.model.objects import Price, Quantity, Currency
        from nautilus_trader.model.enums import CurrencyType
        import nautilus_trader.model.currencies as currencies
        from decimal import Decimal

        def get_currency(code: str) -> Currency:
            code = code.upper()
            if hasattr(currencies, code):
                return getattr(currencies, code)
            return Currency(code, 8, 0, code, CurrencyType.CRYPTO)

        try:
            res_json = await self._rest_client.get_symbols_py()
            data = json.loads(res_json)

            if isinstance(data, dict):
                symbols = data.get("data", data)
            else:
                symbols = data

            instruments = []
            for s in symbols:
                symbol_name = s.get("symbol", "")
                if "_" in symbol_name:
                    continue  # Skip margin for v0.1

                base = symbol_name.upper()
                quote = "JPY"
                symbol_str = f"{base}/{quote}"

                tick_size = Decimal(s.get("tickSize", "1"))
                size_step = Decimal(s.get("sizeStep", "0.0001"))
                p_prec = max(0, -tick_size.as_tuple().exponent)
                q_prec = max(0, -size_step.as_tuple().exponent)
                min_q = s.get("minOrderSize", "0.0001")

                instrument = CurrencyPair(
                    instrument_id=InstrumentId.from_str(f"{symbol_str}.GMOCOIN"),
                    raw_symbol=Symbol(symbol_name),
                    base_currency=get_currency(base),
                    quote_currency=get_currency(quote),
                    price_precision=p_prec,
                    size_precision=q_prec,
                    price_increment=Price(tick_size, p_prec),
                    size_increment=Quantity(size_step, q_prec),
                    min_quantity=Quantity.from_str(str(min_q)),
                    ts_event=0,
                    ts_init=0,
                )
                instruments.append(instrument)

            self._logger.info(f"Fetched {len(instruments)} instruments from GMO Coin")
            return instruments

        except Exception as e:
            self._logger.error(f"Error fetching instruments: {e}")
            return []

    async def _subscribe_quote_ticks(self, command):
        instrument_id = command.instrument_id if hasattr(command, 'instrument_id') else command
        instrument = self._instrument_provider.find(instrument_id)
        if instrument is None and hasattr(self, '_cache'):
            instrument = self._cache.instrument(instrument_id)

        if instrument:
            await self.subscribe([instrument])
        else:
            self._logger.error(f"Could not find instrument {instrument_id}")

    async def _unsubscribe_quote_ticks(self, instrument_id):
        pass

    async def _subscribe_trade_ticks(self, command):
        instrument_id = command.instrument_id if hasattr(command, 'instrument_id') else command
        instrument = self._instrument_provider.find(instrument_id)
        if instrument is None and hasattr(self, '_cache'):
            instrument = self._cache.instrument(instrument_id)

        if instrument:
            await self.subscribe([instrument])
        else:
            self._logger.error(f"Could not find instrument {instrument_id}")

    async def _unsubscribe_trade_ticks(self, instrument_id):
        pass

    async def _subscribe_order_book_deltas(self, command):
        instrument_id = command.instrument_id if hasattr(command, 'instrument_id') else command
        instrument = self._instrument_provider.find(instrument_id)
        if instrument is None and hasattr(self, '_cache'):
            instrument = self._cache.instrument(instrument_id)

        if instrument:
            await self.subscribe([instrument])
        else:
            self._logger.error(f"Could not find instrument {instrument_id}")

    async def _unsubscribe_order_book_deltas(self, instrument_id):
        pass

    async def _subscribe_order_book_snapshots(self, instrument_id):
        pass

    async def _subscribe_bars(self, command):
        from nautilus_trader.model.data import BarType
        from nautilus_trader.model.enums import BarAggregation

        bar_type = command.bar_type if hasattr(command, 'bar_type') else command
        spec = bar_type.spec
        step = spec.step
        agg_name = BarAggregation(spec.aggregation).name

        gmo_interval = BAR_SPEC_TO_GMO_INTERVAL.get((step, agg_name))
        if gmo_interval is None:
            self._logger.warning(
                f"Unsupported bar specification: {step}-{agg_name}. "
                f"Supported: {list(BAR_SPEC_TO_GMO_INTERVAL.keys())}"
            )
            return

        bar_type_str = str(bar_type)
        if bar_type_str in self._bar_poll_tasks:
            self._logger.info(f"Already subscribed to bars: {bar_type_str}")
            return

        instrument_id = bar_type.instrument_id
        gmo_symbol = instrument_id.symbol.value.split("/")[0]
        poll_interval = BAR_POLL_INTERVALS.get(gmo_interval, 60)

        self._logger.info(
            f"Subscribing to bars: {bar_type_str} (GMO interval={gmo_interval}, poll={poll_interval}s)"
        )

        task = self.create_task(
            self._bar_poll_loop(bar_type, gmo_symbol, gmo_interval, poll_interval)
        )
        self._bar_poll_tasks[bar_type_str] = task

    async def _unsubscribe_bars(self, command):
        from nautilus_trader.model.data import BarType

        bar_type = command.bar_type if hasattr(command, 'bar_type') else command
        bar_type_str = str(bar_type)

        task = self._bar_poll_tasks.pop(bar_type_str, None)
        if task and not task.done():
            task.cancel()
            self._logger.info(f"Unsubscribed from bars: {bar_type_str}")

    async def _bar_poll_loop(self, bar_type, gmo_symbol: str, gmo_interval: str, poll_interval: int):
        from nautilus_trader.model.data import Bar
        from nautilus_trader.model.objects import Price, Quantity

        bar_type_str = str(bar_type)

        try:
            while True:
                try:
                    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
                    resp_json = await self._rest_client.get_klines_py(gmo_symbol, gmo_interval, date_str)
                    klines = json.loads(resp_json)

                    if isinstance(klines, dict):
                        klines = klines.get("data", klines)
                    if not isinstance(klines, list):
                        klines = []

                    last_ts = self._bar_last_timestamps.get(bar_type_str)

                    for kline in klines:
                        open_time = str(kline.get("openTime", ""))
                        if not open_time:
                            continue

                        if last_ts and open_time <= last_ts:
                            continue

                        ts_event = int(open_time) * 1_000_000  # ms -> ns
                        ts_init = self._clock.timestamp_ns()

                        bar = Bar(
                            bar_type=bar_type,
                            open=Price.from_str(str(kline["open"])),
                            high=Price.from_str(str(kline["high"])),
                            low=Price.from_str(str(kline["low"])),
                            close=Price.from_str(str(kline["close"])),
                            volume=Quantity.from_str(str(kline["volume"])),
                            ts_event=ts_event,
                            ts_init=ts_init,
                        )
                        self._handle_data(bar)
                        self._bar_last_timestamps[bar_type_str] = open_time

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self._logger.error(f"Error polling bars for {bar_type_str}: {e}")

                await asyncio.sleep(poll_interval)

        except asyncio.CancelledError:
            self._logger.info(f"Bar polling stopped for {bar_type_str}")
        except Exception as e:
            self._logger.error(f"Bar poll loop crashed for {bar_type_str}: {e}")

    async def _unsubscribe_order_book_snapshots(self, instrument_id):
        pass

    async def _load_instruments(self):
        if not self.config.instrument_provider or not self.config.instrument_provider.load_ids:
            return

        try:
            import aiohttp
            from nautilus_trader.model.instruments import CurrencyPair
            from nautilus_trader.model.identifiers import Symbol, Venue, InstrumentId
            from nautilus_trader.model.objects import Price, Quantity
            from nautilus_trader.model.currencies import Currency
            from decimal import Decimal
        except ImportError as e:
            self._logger.error(f"Imports failed: {e}")
            return

        def add_instrument(symbol_str: str, base: str, quote: str, p_prec: int, q_prec: int, min_q: str, tick_size, size_step):
            try:
                instrument_id = InstrumentId.from_str(f"{symbol_str}.GMOCOIN")

                exists_in_provider = False
                try:
                    if self._instrument_provider.find(instrument_id):
                        exists_in_provider = True
                except Exception:
                    pass

                instrument = CurrencyPair(
                    instrument_id=instrument_id,
                    raw_symbol=Symbol(symbol_str),
                    base_currency=Currency.from_str(base),
                    quote_currency=Currency.from_str(quote),
                    price_precision=p_prec,
                    size_precision=q_prec,
                    price_increment=Price(tick_size, p_prec),
                    size_increment=Quantity(size_step, q_prec),
                    ts_event=0,
                    ts_init=0,
                    min_quantity=Quantity(Decimal(min_q), q_prec),
                    lot_size=None,
                )

                if not exists_in_provider:
                    self._instrument_provider.add(instrument)
                    self._logger.info(f"Loaded instrument {instrument_id} to provider")

                if self._cache:
                    self._cache.add_instrument(instrument)
            except Exception as e:
                self._logger.error(f"Failed to add instrument {symbol_str}: {e}")

        # Fetch from GMO Coin API
        try:
            res_json = await self._rest_client.get_symbols_py()
            data = json.loads(res_json)
            if isinstance(data, dict):
                symbols = data.get("data", [])
            elif isinstance(data, list):
                symbols = data
            else:
                symbols = []

            symbols_map = {}
            for s in symbols:
                name = s.get("symbol", "")
                if "_" not in name:  # Spot only
                    symbols_map[name.upper()] = s

            for instrument_id_str in self.config.instrument_provider.load_ids:
                try:
                    if "." in instrument_id_str:
                        native_symbol = instrument_id_str.split(".")[0]
                    else:
                        native_symbol = instrument_id_str

                    base = native_symbol.split("/")[0].upper()
                    quote = native_symbol.split("/")[1].upper() if "/" in native_symbol else "JPY"

                    info = symbols_map.get(base)
                    if info:
                        tick_size = Decimal(info.get("tickSize", "1"))
                        size_step = Decimal(info.get("sizeStep", "0.0001"))
                        p_prec = max(0, -tick_size.as_tuple().exponent)
                        q_prec = max(0, -size_step.as_tuple().exponent)
                        min_q = info.get("minOrderSize", "0.0001")
                        add_instrument(f"{base}/{quote}", base, quote, p_prec, q_prec, min_q, tick_size, size_step)
                    else:
                        self._logger.warning(f"Symbol {base} not found in GMO Coin API")
                except Exception as e:
                    self._logger.error(f"Error processing instrument {instrument_id_str}: {e}")

        except Exception as e:
            self._logger.warning(f"Error fetching symbols API: {e}")
