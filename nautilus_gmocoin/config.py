from typing import Optional
from nautilus_trader.config import LiveDataClientConfig, LiveExecClientConfig


class GmocoinDataClientConfig(LiveDataClientConfig):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    timeout_ms: int = 10000
    proxy_url: Optional[str] = None
    order_book_depth: int = 20

    def __post_init__(self):
        if not self.api_key or not self.api_secret:
            raise ValueError("GmocoinDataClientConfig requires both api_key and api_secret")


class GmocoinExecClientConfig(LiveExecClientConfig):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    timeout_ms: int = 10000
    proxy_url: Optional[str] = None

    def __post_init__(self):
        if not self.api_key or not self.api_secret:
            raise ValueError("GmocoinExecClientConfig requires both api_key and api_secret")
