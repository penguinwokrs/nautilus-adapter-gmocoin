"""Integration tests for GMO Coin private REST API (requires API keys).

These tests make real HTTP requests to the GMO Coin API.
Run with: GMOCOIN_API_KEY=... GMOCOIN_API_SECRET=... pytest tests/test_rest_private.py -v

Note: pyo3-asyncio methods need a running event loop at call time,
so we must create the client and call the method inside the async function.
"""
import asyncio
import json
import pytest
from tests.conftest import requires_rust_extension, requires_api_keys, integration, load_api_keys


def _make_rest_client():
    from nautilus_gmocoin import gmocoin
    api_key, api_secret = load_api_keys()
    return gmocoin.GmocoinRestClient(api_key, api_secret, 10000, None, None)


def _run_test(api_call):
    """Run a pyo3-async API call inside a fresh event loop."""
    async def _inner():
        client = _make_rest_client()
        return await api_call(client)
    return asyncio.run(_inner())


@requires_rust_extension
@requires_api_keys
@integration
class TestPrivateRestApi:
    """Tests that call the real GMO Coin private API."""

    def test_get_assets(self):
        result = _run_test(lambda c: c.get_assets_py())
        data = json.loads(result)
        assert isinstance(data, list)
        symbols = [a.get("symbol", "") for a in data]
        assert "JPY" in symbols

    def test_get_margin(self):
        result = _run_test(lambda c: c.get_margin_py())
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "availableAmount" in data or "available_amount" in data

    def test_get_active_orders(self):
        result = _run_test(lambda c: c.get_active_orders_py("BTC", None, None))
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "list" in data

    def test_get_position_summary(self):
        result = _run_test(lambda c: c.get_position_summary_py(None))
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "list" in data

    def test_ws_auth(self):
        result = _run_test(lambda c: c.post_ws_auth_py())
        data = json.loads(result)
        assert isinstance(data, str)
        assert len(data) > 0
