"""Utility for extracting GMO Coin base symbol from NautilusTrader symbol values."""

# Known quote currencies on GMO Coin
_QUOTE_CURRENCIES = ("JPY", "USDT", "USD", "BTC")


def extract_gmo_symbol(symbol_value: str) -> str:
    """Extract base currency from a NautilusTrader symbol value.

    Handles both slash format (``"SOL/JPY"`` → ``"SOL"``) and catalog/compact
    format (``"SOLJPY"`` → ``"SOL"``).  Falls back to the original value if
    no known quote currency suffix is found.

    Parameters
    ----------
    symbol_value : str
        The ``Symbol.value`` string, e.g. ``"BTC/JPY"`` or ``"BTCJPY"``.

    Returns
    -------
    str
        The base currency, e.g. ``"BTC"``, ``"SOL"``.
    """
    if "/" in symbol_value:
        return symbol_value.split("/")[0]
    # Compact / catalog format: strip known quote currency suffix
    upper = symbol_value.upper()
    for qc in _QUOTE_CURRENCIES:
        if upper.endswith(qc) and len(upper) > len(qc):
            return upper[: -len(qc)]
    return symbol_value
