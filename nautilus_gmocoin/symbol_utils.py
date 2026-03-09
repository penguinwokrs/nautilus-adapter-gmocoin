"""Utility for extracting GMO Coin base/quote symbols from NautilusTrader symbol values."""

# Known quote currencies on GMO Coin (sorted longest-first to avoid suffix ambiguity)
_QUOTE_CURRENCIES = sorted(("JPY", "USDT", "USD", "BTC"), key=len, reverse=True)


def extract_gmo_symbol(symbol_value: str) -> str:
    """Extract base currency from a NautilusTrader symbol value.

    Handles both slash format (``"SOL/JPY"`` → ``"SOL"``) and catalog/compact
    format (``"SOLJPY"`` → ``"SOL"``).  Always returns uppercase.
    Falls back to the original value (uppercased) if no known quote currency
    suffix is found.

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
        return symbol_value.split("/")[0].upper()
    # Compact / catalog format: strip known quote currency suffix
    upper = symbol_value.upper()
    for qc in _QUOTE_CURRENCIES:
        if upper.endswith(qc) and len(upper) > len(qc):
            return upper[: -len(qc)]
    return upper


def extract_quote_currency(symbol_value: str) -> str:
    """Extract quote currency from a NautilusTrader symbol value.

    Handles both slash format (``"SOL/JPY"`` → ``"JPY"``) and catalog/compact
    format (``"SOLJPY"`` → ``"JPY"``).  Always returns uppercase.
    Falls back to ``"JPY"`` if no known quote currency suffix is found.

    Parameters
    ----------
    symbol_value : str
        The ``Symbol.value`` string, e.g. ``"BTC/JPY"`` or ``"BTCUSDT"``.

    Returns
    -------
    str
        The quote currency, e.g. ``"JPY"``, ``"USDT"``.
    """
    if "/" in symbol_value:
        return symbol_value.split("/")[1].upper()
    upper = symbol_value.upper()
    for qc in _QUOTE_CURRENCIES:
        if upper.endswith(qc) and len(upper) > len(qc):
            return qc
    return "JPY"
