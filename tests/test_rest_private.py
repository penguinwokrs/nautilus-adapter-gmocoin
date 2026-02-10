"""Integration tests for GMO Coin private REST API (requires API keys).

These tests make real HTTP requests to the GMO Coin API.
Run with: GMOCOIN_API_KEY=... GMOCOIN_API_SECRET=... pytest tests/test_rest_private.py -v
"""
import asyncio
import json
import pytest
from tests.conftest import requires_rust_extension, requires_api_keys, load_api_keys


def run_async(coro):
    """Run a pyo3-asyncio coroutine in a fresh event loop."""
    async def wrapper():
        return await coro
    return asyncio.run(wrapper())


@requires_rust_extension
@requires_api_keys
class TestPrivateRestApi:
    """Tests that call the real GMO Coin private API."""

    @pytest.fixture
    def rest_client(self):
        from nautilus_gmocoin import gmocoin
        api_key, api_secret = load_api_keys()
        return gmocoin.GmocoinRestClient(api_key, api_secret, 10000, None, None)

    def test_get_assets(self, rest_client):
        result = run_async(rest_client.get_assets_py())
        data = json.loads(result)
        assert isinstance(data, list)
        symbols = [a.get("symbol", "") for a in data]
        assert "JPY" in symbols

    def test_get_margin(self, rest_client):
        result = run_async(rest_client.get_margin_py())
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "availableAmount" in data or "available_amount" in data

    def test_get_active_orders(self, rest_client):
        result = run_async(rest_client.get_active_orders_py("BTC", None, None))
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "list" in data

    def test_get_position_summary(self, rest_client):
        result = run_async(rest_client.get_position_summary_py(None))
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "list" in data

    def test_ws_auth(self, rest_client):
        result = run_async(rest_client.post_ws_auth_py())
        data = json.loads(result)
        assert isinstance(data, str)
        assert len(data) > 0
