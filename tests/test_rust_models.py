"""Tests for Rust PyO3 model types (requires maturin develop)."""
import pytest
from tests.conftest import requires_rust_extension


@requires_rust_extension
class TestTicker:
    def test_create(self):
        from nautilus_gmocoin import gmocoin
        ticker = gmocoin.Ticker(
            ask="5000100",
            bid="5000000",
            high="5100000",
            low="4900000",
            last="5000050",
            symbol="BTC",
            timestamp="2024-01-01T00:00:00.000Z",
            volume="123.456",
        )
        assert ticker.ask == "5000100"
        assert ticker.bid == "5000000"
        assert ticker.high == "5100000"
        assert ticker.low == "4900000"
        assert ticker.last == "5000050"
        assert ticker.symbol == "BTC"
        assert ticker.volume == "123.456"


@requires_rust_extension
class TestTrade:
    def test_create(self):
        from nautilus_gmocoin import gmocoin
        trade = gmocoin.Trade(
            price="5000000",
            side="BUY",
            size="0.01",
            timestamp="2024-01-01T00:00:00.000Z",
            symbol="BTC",
        )
        assert trade.price == "5000000"
        assert trade.side == "BUY"
        assert trade.size == "0.01"
        assert trade.symbol == "BTC"

    def test_create_without_symbol(self):
        from nautilus_gmocoin import gmocoin
        trade = gmocoin.Trade(
            price="100",
            side="SELL",
            size="1.0",
            timestamp="2024-01-01T00:00:00.000Z",
            symbol=None,
        )
        assert trade.symbol is None


@requires_rust_extension
class TestSymbolInfo:
    def test_create_minimal(self):
        from nautilus_gmocoin import gmocoin
        info = gmocoin.SymbolInfo(symbol="BTC")
        assert info.symbol == "BTC"
        assert info.min_order_size is None
        assert info.tick_size is None
        assert info.size_step is None


@requires_rust_extension
class TestOrderBook:
    def test_create(self):
        from nautilus_gmocoin import gmocoin
        book = gmocoin.OrderBook(symbol="BTC")
        assert book.symbol == "BTC"

    def test_get_top_n_empty(self):
        from nautilus_gmocoin import gmocoin
        book = gmocoin.OrderBook(symbol="BTC")
        asks, bids = book.get_top_n(5)
        assert asks == []
        assert bids == []


@requires_rust_extension
class TestRestClientCreate:
    def test_create(self):
        from nautilus_gmocoin import gmocoin
        client = gmocoin.GmocoinRestClient(
            "test_key", "test_secret", 10000, None, None
        )
        assert client is not None

    def test_create_with_rate_limit(self):
        from nautilus_gmocoin import gmocoin
        client = gmocoin.GmocoinRestClient(
            "test_key", "test_secret", 5000, None, 30.0
        )
        assert client is not None


@requires_rust_extension
class TestDataClientCreate:
    def test_create(self):
        from nautilus_gmocoin import gmocoin
        client = gmocoin.GmocoinDataClient(None)
        assert client is not None

    def test_create_with_rate_limit(self):
        from nautilus_gmocoin import gmocoin
        client = gmocoin.GmocoinDataClient(1.0)
        assert client is not None


@requires_rust_extension
class TestExecutionClientCreate:
    def test_create(self):
        from nautilus_gmocoin import gmocoin
        client = gmocoin.GmocoinExecutionClient(
            "test_key", "test_secret", 10000, None, None
        )
        assert client is not None
