"""
Factory classes for GMO Coin Data and Execution clients.
Used by TradingNode to instantiate the clients.
"""

from nautilus_trader.live.factories import LiveDataClientFactory, LiveExecClientFactory
from nautilus_trader.common.providers import InstrumentProvider

from .data import GmocoinDataClient
from .execution import GmocoinExecutionClient


class GmocoinDataClientFactory(LiveDataClientFactory):
    """Factory for creating GmocoinDataClient instances."""

    @classmethod
    def create(cls, loop, msgbus, cache, clock, instrument_provider=None, name=None, config=None, **kwargs):
        if config is None:
            raise ValueError("Config required for GmocoinDataClient")
        return GmocoinDataClient(loop, config, msgbus, cache, clock, instrument_provider)


class GmocoinExecutionClientFactory(LiveExecClientFactory):
    """Factory for creating GmocoinExecutionClient instances."""

    @classmethod
    def create(cls, loop, msgbus, cache, clock, instrument_provider=None, name=None, config=None, **kwargs):
        if config is None:
            raise ValueError("Config required for GmocoinExecutionClient")

        if instrument_provider is None:
            if isinstance(cache, InstrumentProvider):
                instrument_provider = cache
            else:
                class CacheWrapper(InstrumentProvider):
                    def __init__(self, inner_cache):
                        super().__init__()
                        self._cache = inner_cache

                    def instrument(self, instrument_id):
                        return self._cache.instrument(instrument_id)

                    def currency(self, code):
                        if hasattr(self._cache, "currency"):
                            return self._cache.currency(code)
                        from nautilus_trader.model import currencies
                        return getattr(currencies, code, None)

                    def add_currency(self, currency):
                        if hasattr(self._cache, "add_currency"):
                            return self._cache.add_currency(currency)

                instrument_provider = CacheWrapper(cache)

        return GmocoinExecutionClient(loop, config, msgbus, cache, clock, instrument_provider)
