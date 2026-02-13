"""Integration tests for GMO Coin private REST API (requires API keys).

These tests make real HTTP requests to the GMO Coin API when recording.
In replay mode (default), responses are loaded from cassette files.

Record cassettes:
    GMOCOIN_API_KEY=... GMOCOIN_API_SECRET=... pytest tests/test_rest_private.py --record-cassettes -v
Replay (default):
    pytest tests/test_rest_private.py -v
"""
import asyncio
import json
from tests.conftest import requires_rust_extension, integration, load_api_keys


def _make_rest_client():
    from nautilus_gmocoin import gmocoin
    api_key, api_secret = load_api_keys()
    return gmocoin.GmocoinRestClient(api_key, api_secret, 10000, None, None)


def _live(api_call):
    """Wrap an API call for vcr recording: creates client and runs in event loop."""
    def _run():
        async def _inner():
            client = _make_rest_client()
            return await api_call(client)
        return asyncio.run(_inner())
    return _run


@requires_rust_extension
@integration
class TestPrivateRestApi:
    """Tests that call the real GMO Coin private API."""

    def test_get_assets(self, vcr):
        result = vcr(_live(lambda c: c.get_assets_py()))
        data = json.loads(result)
        assert isinstance(data, list)
        symbols = [a.get("symbol", "") for a in data]
        assert "JPY" in symbols

    def test_get_margin(self, vcr):
        result = vcr(_live(lambda c: c.get_margin_py()))
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "availableAmount" in data or "available_amount" in data

    def test_get_active_orders(self, vcr):
        result = vcr(_live(lambda c: c.get_active_orders_py("BTC", None, None)))
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "list" in data

    def test_get_position_summary(self, vcr):
        result = vcr(_live(lambda c: c.get_position_summary_py(None)))
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "list" in data

    def test_ws_auth(self, vcr):
        result = vcr(_live(lambda c: c.post_ws_auth_py()))
        data = json.loads(result)
        assert isinstance(data, str)
        assert len(data) > 0
