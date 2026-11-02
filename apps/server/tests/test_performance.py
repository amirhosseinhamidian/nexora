from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from uuid import UUID

import pytest
from nexora.holdings_projection import CostBasisMethod
from nexora.performance import (
    PERFORMANCE_POLICY_VERSION,
    AnalyticsState,
    AnalyticsValidationError,
    ExternalFlow,
    PerformancePointState,
    PortfolioAnalyticsSnapshot,
    bounded_series_times,
    calculate_performance_points,
)

PORTFOLIO_ID = UUID("00000000-0000-0000-0000-000000000101")
BASE_ASSET_ID = UUID("00000000-0000-0000-0000-000000000301")
START = datetime(2026, 11, 1, tzinfo=UTC)


def _snapshot(
    offset: int, nav: str | None, state: AnalyticsState = AnalyticsState.COMPLETE
) -> PortfolioAnalyticsSnapshot:
    amount = None if nav is None else Decimal(nav)
    return PortfolioAnalyticsSnapshot(
        PORTFOLIO_ID,
        BASE_ASSET_ID,
        START + timedelta(days=offset),
        CostBasisMethod.FIFO,
        PERFORMANCE_POLICY_VERSION,
        str(offset) * 64,
        offset,
        state,
        amount,
        amount or Decimal(0),
        Decimal(0),
        Decimal(0),
        (),
        (),
    )


def test_flow_adjusted_returns_are_chain_linked_with_exact_decimal_arithmetic() -> None:
    snapshots = (_snapshot(0, "100"), _snapshot(1, "120"), _snapshot(2, "121"))
    flow = ExternalFlow(
        UUID("00000000-0000-0000-0000-000000000501"),
        START + timedelta(hours=12),
        Decimal("10"),
        AnalyticsState.COMPLETE,
        None,
    )
    points = calculate_performance_points(snapshots, ((flow,), ()))
    assert points[1].external_flow == Decimal("10")
    assert points[1].period_return == Decimal("0.1")
    with localcontext() as context:
        context.prec = 200
        expected_period = Decimal(1) / Decimal(120)
        expected_cumulative = (Decimal("1.1") * (Decimal(1) + expected_period)) - Decimal(1)
    assert points[2].period_return == expected_period
    assert points[2].cumulative_return == expected_cumulative
    assert all(point.state is PerformancePointState.AVAILABLE for point in points)


def test_missing_flow_valuation_makes_the_subperiod_and_chain_unavailable() -> None:
    missing_flow = ExternalFlow(
        UUID("00000000-0000-0000-0000-000000000501"),
        START + timedelta(hours=12),
        None,
        AnalyticsState.MISSING,
        "MISSING_EXTERNAL_FLOW_VALUATION",
    )
    points = calculate_performance_points((_snapshot(0, "100"), _snapshot(1, "120")), ((missing_flow,),))
    assert points[1].state is PerformancePointState.UNAVAILABLE
    assert points[1].period_return is None
    assert points[1].cumulative_return is None
    assert points[1].reason_code == "MISSING_EXTERNAL_FLOW_VALUATION"


def test_stale_evidence_remains_visible_on_an_available_return() -> None:
    points = calculate_performance_points(
        (_snapshot(0, "100"), _snapshot(1, "110", AnalyticsState.STALE)),
        ((),),
    )
    assert points[1].period_return == Decimal("0.1")
    assert points[1].state is PerformancePointState.STALE


@pytest.mark.parametrize("point_count", [1, 33])
def test_series_point_count_is_bounded(point_count: int) -> None:
    with pytest.raises(AnalyticsValidationError, match="point count"):
        bounded_series_times(START, START + timedelta(days=1), point_count)


def test_series_range_is_chronological_and_limited_to_366_days() -> None:
    with pytest.raises(AnalyticsValidationError, match="follow start"):
        bounded_series_times(START, START, 2)
    with pytest.raises(AnalyticsValidationError, match="366 days"):
        bounded_series_times(START, START + timedelta(days=367), 2)
    with pytest.raises(AnalyticsValidationError, match="366 days"):
        bounded_series_times(START, START + timedelta(days=366, seconds=1), 2)
    points = bounded_series_times(START, START + timedelta(days=2), 3)
    assert points == (START, START + timedelta(days=1), START + timedelta(days=2))
