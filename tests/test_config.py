"""Tests for nautilus_gmocoin.config."""
import pytest
from nautilus_gmocoin.config import GmocoinDataClientConfig, GmocoinExecClientConfig


class TestGmocoinDataClientConfig:
    def test_valid_config(self):
        config = GmocoinDataClientConfig(api_key="test_key", api_secret="test_secret")
        assert config.api_key == "test_key"
        assert config.api_secret == "test_secret"

    def test_default_values(self):
        config = GmocoinDataClientConfig(api_key="key", api_secret="secret")
        assert config.timeout_ms == 10000
        assert config.proxy_url is None
        assert config.order_book_depth == 20
        assert config.rate_limit_per_sec is None
        assert config.ws_rate_limit_per_sec is None
        assert config.trades_taker_only is False

    def test_custom_values(self):
        config = GmocoinDataClientConfig(
            api_key="key",
            api_secret="secret",
            timeout_ms=5000,
            order_book_depth=10,
            rate_limit_per_sec=30.0,
            ws_rate_limit_per_sec=1.0,
            trades_taker_only=True,
        )
        assert config.timeout_ms == 5000
        assert config.order_book_depth == 10
        assert config.rate_limit_per_sec == 30.0
        assert config.ws_rate_limit_per_sec == 1.0
        assert config.trades_taker_only is True


class TestGmocoinExecClientConfig:
    def test_valid_config(self):
        config = GmocoinExecClientConfig(api_key="test_key", api_secret="test_secret")
        assert config.api_key == "test_key"
        assert config.api_secret == "test_secret"

    def test_default_values(self):
        config = GmocoinExecClientConfig(api_key="key", api_secret="secret")
        assert config.timeout_ms == 10000
        assert config.proxy_url is None
        assert config.rate_limit_per_sec is None

    def test_custom_rate_limit(self):
        config = GmocoinExecClientConfig(
            api_key="key",
            api_secret="secret",
            rate_limit_per_sec=30.0,
        )
        assert config.rate_limit_per_sec == 30.0
