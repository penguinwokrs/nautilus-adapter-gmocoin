"""Tests for bar interval mapping logic used by _subscribe_bars."""
import pytest
from nautilus_trader.model.enums import BarAggregation
from nautilus_gmocoin.constants import BAR_SPEC_TO_GMO_INTERVAL


def bar_spec_to_gmo_interval(step: int, aggregation: BarAggregation) -> str | None:
    """Replicate the mapping logic from data.py _subscribe_bars."""
    agg_name = BarAggregation(aggregation).name
    return BAR_SPEC_TO_GMO_INTERVAL.get((step, agg_name))


class TestBarSpecMapping:
    @pytest.mark.parametrize("step,agg,expected", [
        (1, BarAggregation.MINUTE, "1min"),
        (5, BarAggregation.MINUTE, "5min"),
        (10, BarAggregation.MINUTE, "10min"),
        (15, BarAggregation.MINUTE, "15min"),
        (30, BarAggregation.MINUTE, "30min"),
        (1, BarAggregation.HOUR, "1hour"),
        (4, BarAggregation.HOUR, "4hour"),
        (8, BarAggregation.HOUR, "8hour"),
        (12, BarAggregation.HOUR, "12hour"),
        (1, BarAggregation.DAY, "1day"),
        (1, BarAggregation.WEEK, "1week"),
        (1, BarAggregation.MONTH, "1month"),
    ])
    def test_valid_bar_specs(self, step, agg, expected):
        result = bar_spec_to_gmo_interval(step, agg)
        assert result == expected

    @pytest.mark.parametrize("step,agg", [
        (2, BarAggregation.MINUTE),
        (3, BarAggregation.MINUTE),
        (7, BarAggregation.MINUTE),
        (2, BarAggregation.HOUR),
        (6, BarAggregation.HOUR),
        (2, BarAggregation.DAY),
        (1, BarAggregation.SECOND),
        (1, BarAggregation.TICK),
    ])
    def test_unsupported_bar_specs_return_none(self, step, agg):
        result = bar_spec_to_gmo_interval(step, agg)
        assert result is None
