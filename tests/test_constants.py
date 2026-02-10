"""Tests for nautilus_gmocoin.constants."""
import pytest
from nautilus_gmocoin.constants import (
    GMOCOIN_VENUE,
    ORDER_STATUS_MAP,
    ORDER_SIDE_MAP,
    ORDER_TYPE_MAP,
    NAUTILUS_TO_GMO_ORDER_TYPE,
    TIME_IN_FORCE_MAP,
    KLINE_INTERVALS,
    BAR_SPEC_TO_GMO_INTERVAL,
    BAR_POLL_INTERVALS,
)


class TestVenue:
    def test_venue_value(self):
        assert GMOCOIN_VENUE.value == "GMOCOIN"


class TestOrderStatusMap:
    @pytest.mark.parametrize("gmo_status,nautilus_status", [
        ("WAITING", "ACCEPTED"),
        ("ORDERED", "ACCEPTED"),
        ("MODIFYING", "ACCEPTED"),
        ("CANCELLING", "PENDING_CANCEL"),
        ("CANCELED", "CANCELED"),
        ("EXECUTED", "FILLED"),
        ("EXPIRED", "EXPIRED"),
    ])
    def test_order_status_mapping(self, gmo_status, nautilus_status):
        assert ORDER_STATUS_MAP[gmo_status] == nautilus_status

    def test_all_gmo_statuses_mapped(self):
        expected_statuses = {"WAITING", "ORDERED", "MODIFYING", "CANCELLING", "CANCELED", "EXECUTED", "EXPIRED"}
        assert set(ORDER_STATUS_MAP.keys()) == expected_statuses


class TestOrderSideMap:
    def test_buy(self):
        assert ORDER_SIDE_MAP["BUY"] == "BUY"

    def test_sell(self):
        assert ORDER_SIDE_MAP["SELL"] == "SELL"


class TestOrderTypeMap:
    @pytest.mark.parametrize("gmo_type,nautilus_type", [
        ("MARKET", "MARKET"),
        ("LIMIT", "LIMIT"),
        ("STOP", "STOP_MARKET"),
    ])
    def test_order_type_mapping(self, gmo_type, nautilus_type):
        assert ORDER_TYPE_MAP[gmo_type] == nautilus_type

    @pytest.mark.parametrize("nautilus_type,gmo_type", [
        ("MARKET", "MARKET"),
        ("LIMIT", "LIMIT"),
        ("STOP_MARKET", "STOP"),
    ])
    def test_reverse_mapping(self, nautilus_type, gmo_type):
        assert NAUTILUS_TO_GMO_ORDER_TYPE[nautilus_type] == gmo_type

    def test_roundtrip(self):
        for gmo, nautilus in ORDER_TYPE_MAP.items():
            assert NAUTILUS_TO_GMO_ORDER_TYPE[nautilus] == gmo


class TestTimeInForceMap:
    @pytest.mark.parametrize("gmo_tif,nautilus_tif", [
        ("FAK", "IOC"),
        ("FAS", "GTC"),
        ("FOK", "FOK"),
        ("SOK", "GTC"),
    ])
    def test_time_in_force_mapping(self, gmo_tif, nautilus_tif):
        assert TIME_IN_FORCE_MAP[gmo_tif] == nautilus_tif


class TestKlineIntervals:
    def test_all_intervals_present(self):
        expected = [
            "1min", "5min", "10min", "15min", "30min",
            "1hour", "4hour", "8hour", "12hour",
            "1day", "1week", "1month",
        ]
        assert KLINE_INTERVALS == expected


class TestBarSpecToGmoInterval:
    @pytest.mark.parametrize("step,agg,expected_interval", [
        (1, "MINUTE", "1min"),
        (5, "MINUTE", "5min"),
        (10, "MINUTE", "10min"),
        (15, "MINUTE", "15min"),
        (30, "MINUTE", "30min"),
        (1, "HOUR", "1hour"),
        (4, "HOUR", "4hour"),
        (8, "HOUR", "8hour"),
        (12, "HOUR", "12hour"),
        (1, "DAY", "1day"),
        (1, "WEEK", "1week"),
        (1, "MONTH", "1month"),
    ])
    def test_valid_mappings(self, step, agg, expected_interval):
        assert BAR_SPEC_TO_GMO_INTERVAL[(step, agg)] == expected_interval

    @pytest.mark.parametrize("step,agg", [
        (2, "MINUTE"),
        (3, "HOUR"),
        (2, "DAY"),
        (1, "SECOND"),
    ])
    def test_unsupported_specs(self, step, agg):
        assert (step, agg) not in BAR_SPEC_TO_GMO_INTERVAL

    def test_all_mapped_intervals_are_valid_kline_intervals(self):
        for interval in BAR_SPEC_TO_GMO_INTERVAL.values():
            assert interval in KLINE_INTERVALS


class TestBarPollIntervals:
    def test_all_kline_intervals_have_poll_interval(self):
        for interval in KLINE_INTERVALS:
            assert interval in BAR_POLL_INTERVALS

    def test_poll_intervals_are_positive(self):
        for interval, poll_sec in BAR_POLL_INTERVALS.items():
            assert poll_sec > 0, f"Poll interval for {interval} should be positive"

    def test_shorter_bars_poll_more_frequently(self):
        assert BAR_POLL_INTERVALS["1min"] < BAR_POLL_INTERVALS["1hour"]
        assert BAR_POLL_INTERVALS["1hour"] < BAR_POLL_INTERVALS["1day"]
