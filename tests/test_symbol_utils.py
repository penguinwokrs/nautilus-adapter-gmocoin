"""Tests for symbol_utils.extract_gmo_symbol."""

import pytest
from nautilus_gmocoin.symbol_utils import extract_gmo_symbol


@pytest.mark.parametrize(
    "input_val, expected",
    [
        # Slash format (standard NautilusTrader)
        ("BTC/JPY", "BTC"),
        ("SOL/JPY", "SOL"),
        ("XRP/JPY", "XRP"),
        ("ETH/JPY", "ETH"),
        ("DOGE/JPY", "DOGE"),
        ("BTC/USDT", "BTC"),
        # Compact / catalog format (no slash)
        ("BTCJPY", "BTC"),
        ("SOLJPY", "SOL"),
        ("XRPJPY", "XRP"),
        ("ETHJPY", "ETH"),
        ("DOGEJPY", "DOGE"),
        ("BTCUSDT", "BTC"),
        # Edge: already base only
        ("BTC", "BTC"),
        ("SOL", "SOL"),
    ],
)
def test_extract_gmo_symbol(input_val: str, expected: str):
    assert extract_gmo_symbol(input_val) == expected
