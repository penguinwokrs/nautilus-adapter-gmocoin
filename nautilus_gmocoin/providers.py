# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2024 Penguinworks. All rights reserved.
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
# -------------------------------------------------------------------------------------------------
"""
GMO Coin instrument provider implementation.
"""

from decimal import Decimal
import json
import logging

from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Currency, Price, Quantity

GMOCOIN_VENUE = Venue("GMOCOIN")

logger = logging.getLogger(__name__)


class GmocoinInstrumentProvider(InstrumentProvider):
    """
    Provides Nautilus instrument definitions from GMO Coin.

    Parameters
    ----------
    client : GmocoinRestClient
        The GMO Coin REST client (Rust backend).
    config : InstrumentProviderConfig, optional
        The instrument provider configuration.
    """

    def __init__(
        self,
        client,
        config: InstrumentProviderConfig | None = None,
    ) -> None:
        super().__init__(config=config)
        self._client = client
        self._log_warnings = config.log_warnings if config else True

    async def load_all_async(self, filters: dict | None = None) -> None:
        filters_str = "..." if not filters else f" with filters {filters}..."
        self._log.info(f"Loading all instruments{filters_str}")

        try:
            symbols_json = await self._client.get_symbols_py()
            symbols_data = json.loads(symbols_json)

            if isinstance(symbols_data, dict):
                symbols_data = symbols_data.get("data", symbols_data)

            if not isinstance(symbols_data, list):
                symbols_data = []

            for symbol_info in symbols_data:
                try:
                    instrument = self._parse_instrument(symbol_info)
                    if instrument:
                        self.add(instrument=instrument)
                except Exception as e:
                    if self._log_warnings:
                        self._log.warning(f"Failed to parse instrument: {e}")

            self._log.info(f"Loaded {len(self._instruments)} instruments from GMO Coin")

        except Exception as e:
            self._log.error(f"Failed to load instruments: {e}")
            raise

    async def load_ids_async(
        self,
        instrument_ids: list[InstrumentId],
        filters: dict | None = None,
    ) -> None:
        if not instrument_ids:
            self._log.warning("No instrument IDs given for loading")
            return

        for instrument_id in instrument_ids:
            if instrument_id.venue != GMOCOIN_VENUE:
                raise ValueError(
                    f"Instrument {instrument_id} is not for GMOCOIN venue"
                )

        await self.load_all_async(filters)

        requested_ids = set(instrument_ids)
        for instrument_id in list(self._instruments.keys()):
            if instrument_id not in requested_ids:
                self._instruments.pop(instrument_id, None)

    async def load_async(
        self,
        instrument_id: InstrumentId,
        filters: dict | None = None,
    ) -> None:
        await self.load_ids_async([instrument_id], filters)

    def _parse_instrument(self, symbol_info: dict) -> CurrencyPair | None:
        symbol_name = symbol_info.get("symbol", "")
        if not symbol_name:
            return None

        # GMO Coin spot symbols: "BTC", "ETH", etc. (always vs JPY)
        # Margin symbols: "BTC_JPY", "ETH_JPY" (skip for v0.1)
        if "_" in symbol_name:
            return None  # Skip margin symbols for v0.1

        base_asset = symbol_name.upper()
        quote_asset = "JPY"

        # Parse precision from tickSize and sizeStep
        tick_size_str = symbol_info.get("tickSize") or symbol_info.get("tick_size") or "1"
        size_step_str = symbol_info.get("sizeStep") or symbol_info.get("size_step") or "0.0001"

        tick_size = Decimal(tick_size_str)
        size_step = Decimal(size_step_str)

        price_precision = max(0, -tick_size.as_tuple().exponent)
        size_precision = max(0, -size_step.as_tuple().exponent)

        # Parse fees
        maker_fee = Decimal(symbol_info.get("makerFee") or symbol_info.get("maker_fee") or "0")
        taker_fee = Decimal(symbol_info.get("takerFee") or symbol_info.get("taker_fee") or "0")

        # Min/max amounts
        min_order_size = symbol_info.get("minOrderSize") or symbol_info.get("min_order_size") or "0.0001"
        max_order_size = symbol_info.get("maxOrderSize") or symbol_info.get("max_order_size")

        # Symbol string
        symbol_str = f"{base_asset}/{quote_asset}"

        instrument_id = InstrumentId(
            symbol=Symbol(symbol_str),
            venue=GMOCOIN_VENUE,
        )

        # Currencies
        from nautilus_trader.model.enums import CurrencyType

        base_currency = Currency(
            code=base_asset,
            precision=size_precision,
            iso4217=0,
            name=base_asset,
            currency_type=CurrencyType.CRYPTO,
        )
        quote_currency = Currency(
            code=quote_asset,
            precision=price_precision,
            iso4217=392,
            name=quote_asset,
            currency_type=CurrencyType.FIAT,
        )

        price_increment = Price(tick_size, precision=price_precision)
        size_increment = Quantity(size_step, precision=size_precision)

        return CurrencyPair(
            instrument_id=instrument_id,
            raw_symbol=Symbol(symbol_name),
            base_currency=base_currency,
            quote_currency=quote_currency,
            price_precision=price_precision,
            size_precision=size_precision,
            price_increment=price_increment,
            size_increment=size_increment,
            lot_size=Quantity(1, precision=0),
            max_quantity=Quantity.from_str(max_order_size) if max_order_size else None,
            min_quantity=Quantity.from_str(str(min_order_size)),
            max_price=None,
            min_price=None,
            margin_init=Decimal("0"),
            margin_maint=Decimal("0"),
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            ts_event=0,
            ts_init=0,
        )
