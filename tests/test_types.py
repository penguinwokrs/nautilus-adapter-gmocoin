"""Tests for nautilus_gmocoin.types."""
import pytest
from decimal import Decimal
from nautilus_gmocoin.types import (
    GmocoinOrderStatus,
    GmocoinOrderSide,
    GmocoinOrderType,
    GmocoinTimeInForce,
    GmocoinOrderInfo,
    GmocoinAsset,
    GmocoinExecution,
)


class TestGmocoinOrderStatus:
    @pytest.mark.parametrize("value,expected", [
        ("WAITING", GmocoinOrderStatus.WAITING),
        ("ORDERED", GmocoinOrderStatus.ORDERED),
        ("MODIFYING", GmocoinOrderStatus.MODIFYING),
        ("CANCELLING", GmocoinOrderStatus.CANCELLING),
        ("CANCELED", GmocoinOrderStatus.CANCELED),
        ("EXECUTED", GmocoinOrderStatus.EXECUTED),
        ("EXPIRED", GmocoinOrderStatus.EXPIRED),
    ])
    def test_from_str(self, value, expected):
        assert GmocoinOrderStatus.from_str(value) == expected

    def test_from_str_case_insensitive(self):
        assert GmocoinOrderStatus.from_str("waiting") == GmocoinOrderStatus.WAITING
        assert GmocoinOrderStatus.from_str("Executed") == GmocoinOrderStatus.EXECUTED

    def test_from_str_unknown_defaults_to_waiting(self):
        assert GmocoinOrderStatus.from_str("UNKNOWN") == GmocoinOrderStatus.WAITING


class TestGmocoinOrderSide:
    def test_from_str_buy(self):
        assert GmocoinOrderSide.from_str("BUY") == GmocoinOrderSide.BUY

    def test_from_str_sell(self):
        assert GmocoinOrderSide.from_str("SELL") == GmocoinOrderSide.SELL

    def test_from_str_case_insensitive(self):
        assert GmocoinOrderSide.from_str("buy") == GmocoinOrderSide.BUY
        assert GmocoinOrderSide.from_str("Sell") == GmocoinOrderSide.SELL

    def test_from_str_unknown_defaults_to_sell(self):
        assert GmocoinOrderSide.from_str("UNKNOWN") == GmocoinOrderSide.SELL


class TestGmocoinOrderType:
    @pytest.mark.parametrize("value,expected", [
        ("MARKET", GmocoinOrderType.MARKET),
        ("LIMIT", GmocoinOrderType.LIMIT),
        ("STOP", GmocoinOrderType.STOP),
    ])
    def test_from_str(self, value, expected):
        assert GmocoinOrderType.from_str(value) == expected

    def test_from_str_case_insensitive(self):
        assert GmocoinOrderType.from_str("limit") == GmocoinOrderType.LIMIT

    def test_from_str_unknown_defaults_to_market(self):
        assert GmocoinOrderType.from_str("UNKNOWN") == GmocoinOrderType.MARKET


class TestGmocoinTimeInForce:
    def test_enum_values(self):
        assert GmocoinTimeInForce.FAK.value == "FAK"
        assert GmocoinTimeInForce.FAS.value == "FAS"
        assert GmocoinTimeInForce.FOK.value == "FOK"
        assert GmocoinTimeInForce.SOK.value == "SOK"


class TestGmocoinOrderInfo:
    def _make_order(self, **kwargs):
        defaults = dict(
            order_id=12345,
            symbol="BTC",
            side=GmocoinOrderSide.BUY,
            execution_type=GmocoinOrderType.LIMIT,
            size=Decimal("0.01"),
            executed_size=Decimal("0"),
            price=Decimal("5000000"),
            status=GmocoinOrderStatus.ORDERED,
            timestamp="2024-01-01T00:00:00.000Z",
        )
        defaults.update(kwargs)
        return GmocoinOrderInfo(**defaults)

    def test_is_open_waiting(self):
        order = self._make_order(status=GmocoinOrderStatus.WAITING)
        assert order.is_open is True

    def test_is_open_ordered(self):
        order = self._make_order(status=GmocoinOrderStatus.ORDERED)
        assert order.is_open is True

    def test_is_open_modifying(self):
        order = self._make_order(status=GmocoinOrderStatus.MODIFYING)
        assert order.is_open is True

    def test_is_open_canceled_false(self):
        order = self._make_order(status=GmocoinOrderStatus.CANCELED)
        assert order.is_open is False

    def test_is_open_executed_false(self):
        order = self._make_order(status=GmocoinOrderStatus.EXECUTED)
        assert order.is_open is False

    def test_is_filled(self):
        order = self._make_order(status=GmocoinOrderStatus.EXECUTED)
        assert order.is_filled is True

    def test_is_filled_false(self):
        order = self._make_order(status=GmocoinOrderStatus.ORDERED)
        assert order.is_filled is False

    def test_is_canceled(self):
        order = self._make_order(status=GmocoinOrderStatus.CANCELED)
        assert order.is_canceled is True

    def test_is_canceled_false(self):
        order = self._make_order(status=GmocoinOrderStatus.ORDERED)
        assert order.is_canceled is False


class TestGmocoinAsset:
    def test_locked(self):
        asset = GmocoinAsset(symbol="JPY", amount=Decimal("1000000"), available=Decimal("800000"))
        assert asset.locked == Decimal("200000")

    def test_locked_zero(self):
        asset = GmocoinAsset(symbol="BTC", amount=Decimal("1.5"), available=Decimal("1.5"))
        assert asset.locked == Decimal("0")

    def test_attributes(self):
        asset = GmocoinAsset(symbol="ETH", amount=Decimal("10"), available=Decimal("8"))
        assert asset.symbol == "ETH"
        assert asset.amount == Decimal("10")
        assert asset.available == Decimal("8")


class TestGmocoinExecution:
    def test_attributes(self):
        exe = GmocoinExecution(
            execution_id=999,
            order_id=123,
            symbol="BTC",
            side=GmocoinOrderSide.SELL,
            size=Decimal("0.01"),
            price=Decimal("5000000"),
            fee=Decimal("50"),
            timestamp="2024-01-01T00:00:00.000Z",
        )
        assert exe.execution_id == 999
        assert exe.order_id == 123
        assert exe.symbol == "BTC"
        assert exe.side == GmocoinOrderSide.SELL
        assert exe.fee == Decimal("50")
