"""Tests for symbol_utils.extract_gmo_symbol and extract_quote_currency."""

import pytest
from nautilus_gmocoin.symbol_utils import extract_gmo_symbol, extract_quote_currency


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
        # Lowercase slash format
        ("btc/jpy", "BTC"),
        ("sol/jpy", "SOL"),
        # Lowercase compact format
        ("soljpy", "SOL"),
        ("btcjpy", "BTC"),
        # Mixed case
        ("Btc/Jpy", "BTC"),
        ("BtcJpy", "BTC"),
        # Edge: already base only
        ("BTC", "BTC"),
        ("SOL", "SOL"),
        ("sol", "SOL"),
    ],
)
def test_extract_gmo_symbol(input_val: str, expected: str):
    assert extract_gmo_symbol(input_val) == expected


@pytest.mark.parametrize(
    "input_val, expected",
    [
        # Slash format
        ("BTC/JPY", "JPY"),
        ("SOL/USDT", "USDT"),
        ("ETH/USD", "USD"),
        ("XRP/BTC", "BTC"),
        # Compact format
        ("BTCJPY", "JPY"),
        ("SOLUSDT", "USDT"),
        ("ETHUSD", "USD"),
        ("XRPBTC", "BTC"),
        # Lowercase / mixed case
        ("btc/jpy", "JPY"),
        ("solusdt", "USDT"),
        ("Btc/Jpy", "JPY"),
        # Edge: no known quote → default JPY
        ("BTC", "JPY"),
    ],
)
def test_extract_quote_currency(input_val: str, expected: str):
    assert extract_quote_currency(input_val) == expected
