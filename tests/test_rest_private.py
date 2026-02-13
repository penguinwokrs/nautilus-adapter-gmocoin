"""Integration tests for GMO Coin private REST API (requires API keys).

These tests make real HTTP requests to the GMO Coin API.
Run with: GMOCOIN_API_KEY=... GMOCOIN_API_SECRET=... pytest tests/test_rest_private.py -v

Note: pyo3-asyncio methods need a running event loop at call time,
so we must call the method inside the async function.
"""
import asyncio
import json
import pytest
from tests.conftest import requires_rust_extension, requires_api_keys, load_api_keys


def _make_rest_client():
    from nautilus_gmocoin import gmocoin
    api_key, api_secret = load_api_keys()
    return gmocoin.GmocoinRestClient(api_key, api_secret, 10000, None, None)


@requires_rust_extension
@requires_api_keys
class TestPrivateRestApi:
    """Tests that call the real GMO Coin private API."""

    def test_get_assets(self):
        async def _test():
            client = _make_rest_client()
            return await client.get_assets_py()
        result = asyncio.run(_test())
        data = json.loads(result)
        assert isinstance(data, list)
        symbols = [a.get("symbol", "") for a in data]
        assert "JPY" in symbols

    def test_get_margin(self):
        async def _test():
            client = _make_rest_client()
            return await client.get_margin_py()
        result = asyncio.run(_test())
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "availableAmount" in data or "available_amount" in data

    def test_get_active_orders(self):
        async def _test():
            client = _make_rest_client()
            return await client.get_active_orders_py("BTC", None, None)
        result = asyncio.run(_test())
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "list" in data

    def test_get_position_summary(self):
        async def _test():
            client = _make_rest_client()
            return await client.get_position_summary_py(None)
        result = asyncio.run(_test())
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "list" in data

    def test_ws_auth(self):
        async def _test():
            client = _make_rest_client()
            return await client.post_ws_auth_py()
        result = asyncio.run(_test())
        data = json.loads(result)
        assert isinstance(data, str)
        assert len(data) > 0
