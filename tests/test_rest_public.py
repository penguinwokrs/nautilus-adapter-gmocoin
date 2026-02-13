"""Integration tests for GMO Coin public REST API (no API key needed).

These tests make real HTTP requests to the GMO Coin API.
Run with: pytest tests/test_rest_public.py -v

Note: pyo3-asyncio methods need a running event loop at call time,
so we must create the client and call the method inside the async function.
"""
import asyncio
import json
from tests.conftest import requires_rust_extension, integration


def _make_rest_client():
    from nautilus_gmocoin import gmocoin
    return gmocoin.GmocoinRestClient("", "", 10000, None, None)


def _run_test(api_call):
    """Run a pyo3-async API call inside a fresh event loop."""
    async def _inner():
        client = _make_rest_client()
        return await api_call(client)
    return asyncio.run(_inner())


@requires_rust_extension
@integration
class TestPublicRestApi:
    """Tests that call the real GMO Coin public API."""

    def test_get_status(self):
        result = _run_test(lambda c: c.get_status_py())
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "status" in data

    def test_get_ticker(self):
        result = _run_test(lambda c: c.get_ticker_py("BTC"))
        data = json.loads(result)
        assert isinstance(data, list)
        if len(data) > 0:
            ticker = data[0]
            assert "ask" in ticker
            assert "bid" in ticker
            assert "symbol" in ticker

    def test_get_orderbooks(self):
        result = _run_test(lambda c: c.get_orderbooks_py("BTC"))
        data = json.loads(result)
        assert "asks" in data
        assert "bids" in data
        assert isinstance(data["asks"], list)
        assert isinstance(data["bids"], list)

    def test_get_symbols(self):
        result = _run_test(lambda c: c.get_symbols_py())
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) > 0

        symbols = [s["symbol"] for s in data]
        assert "BTC" in symbols

        btc = next(s for s in data if s["symbol"] == "BTC")
        assert "tickSize" in btc

    def test_get_trades(self):
        result = _run_test(lambda c: c.get_trades_py("BTC", None, None))
        data = json.loads(result)
        assert isinstance(data, (list, dict))

    def test_get_klines(self):
        from datetime import datetime, timezone
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")

        result = _run_test(lambda c: c.get_klines_py("BTC", "1hour", date_str))
        data = json.loads(result)
        assert isinstance(data, list)
        if len(data) > 0:
            kline = data[0]
            assert "open" in kline
            assert "high" in kline
            assert "low" in kline
            assert "close" in kline
            assert "volume" in kline
