from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from enum import StrEnum
from uuid import UUID

from nexora.holdings_projection import BasisStatus, CostBasisMethod
from nexora.valuation import ValuationEvidenceKind, ValuationEvidenceState, aware_utc

PERFORMANCE_POLICY_VERSION = "nexora-nav-pnl-performance-v1"


class AnalyticsState(StrEnum):
    COMPLETE = "complete"
    STALE = "stale"
    MISSING = "missing"


class PerformancePointState(StrEnum):
    AVAILABLE = "available"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class AnalyticsError(RuntimeError):
    """Base error for owner-scoped NAV, P&L and performance calculations."""


class AnalyticsNotFound(AnalyticsError):
    """The requested portfolio is unavailable in the owner scope."""


class AnalyticsValidationError(AnalyticsError):
    """The requested calculation violates a bounded analytics invariant."""


@dataclass(frozen=True, slots=True)
class ResolvedValuation:
    asset_id: UUID
    quote_asset_id: UUID
    as_of: datetime
    state: ValuationEvidenceState
    evidence_kind: ValuationEvidenceKind
    unit_value: Decimal | None
    evidence_ids: tuple[UUID, ...]
    evidence_at: datetime | None
    valid_until: datetime | None
    source_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PositionValue:
    account_id: UUID
    asset_id: UUID
    quantity: Decimal
    valuation: ResolvedValuation
    market_value: Decimal | None
    basis_status: BasisStatus
    cost_basis_asset_id: UUID | None
    cost_basis: Decimal | None
    cost_basis_in_base: Decimal | None
    unrealized_pnl: Decimal | None


@dataclass(frozen=True, slots=True)
class RealizedPnlEvent:
    transaction_id: UUID
    occurred_at: datetime
    proceeds_in_base: Decimal | None
    cost_basis_in_base: Decimal | None
    realized_pnl: Decimal | None
    state: AnalyticsState
    reason_code: str | None


@dataclass(frozen=True, slots=True)
class PortfolioAnalyticsSnapshot:
    portfolio_id: UUID
    base_asset_id: UUID
    as_of: datetime
    cost_basis_method: CostBasisMethod
    policy_version: str
    journal_sha256: str
    journal_transaction_count: int
    state: AnalyticsState
    nav: Decimal | None
    priced_value: Decimal
    realized_pnl: Decimal | None
    unrealized_pnl: Decimal | None
    positions: tuple[PositionValue, ...]
    realized_events: tuple[RealizedPnlEvent, ...]


@dataclass(frozen=True, slots=True)
class ExternalFlow:
    transaction_id: UUID
    occurred_at: datetime
    amount_in_base: Decimal | None
    state: AnalyticsState
    reason_code: str | None


@dataclass(frozen=True, slots=True)
class PerformancePoint:
    as_of: datetime
    nav: Decimal | None
    external_flow: Decimal | None
    period_return: Decimal | None
    cumulative_return: Decimal | None
    state: PerformancePointState
    reason_code: str | None


@dataclass(frozen=True, slots=True)
class PerformanceSeries:
    portfolio_id: UUID
    base_asset_id: UUID
    cost_basis_method: CostBasisMethod
    policy_version: str
    start_at: datetime
    end_at: datetime
    points: tuple[PerformancePoint, ...]


def analytics_state(states: tuple[ValuationEvidenceState, ...]) -> AnalyticsState:
    if any(state is ValuationEvidenceState.MISSING for state in states):
        return AnalyticsState.MISSING
    if any(state is ValuationEvidenceState.STALE for state in states):
        return AnalyticsState.STALE
    return AnalyticsState.COMPLETE


def combine_analytics_states(states: tuple[AnalyticsState, ...]) -> AnalyticsState:
    if any(state is AnalyticsState.MISSING for state in states):
        return AnalyticsState.MISSING
    if any(state is AnalyticsState.STALE for state in states):
        return AnalyticsState.STALE
    return AnalyticsState.COMPLETE


def _decimal_sum(values: tuple[Decimal, ...]) -> Decimal:
    with localcontext() as context:
        context.prec = 200
        return sum(values, Decimal(0))


def calculate_performance_points(
    snapshots: tuple[PortfolioAnalyticsSnapshot, ...],
    flows_by_period: tuple[tuple[ExternalFlow, ...], ...],
) -> tuple[PerformancePoint, ...]:
    if len(snapshots) < 2 or len(flows_by_period) != len(snapshots) - 1:
        raise AnalyticsValidationError("performance requires aligned snapshots and subperiod flows")
    ordered = tuple(sorted(snapshots, key=lambda item: aware_utc(item.as_of)))
    if ordered != snapshots or len({item.as_of for item in snapshots}) != len(snapshots):
        raise AnalyticsValidationError("performance snapshots must be unique and chronological")

    first = snapshots[0]
    initial_state = (
        PerformancePointState.UNAVAILABLE
        if first.nav is None
        else PerformancePointState.STALE
        if first.state is AnalyticsState.STALE
        else PerformancePointState.AVAILABLE
    )
    result = [
        PerformancePoint(
            first.as_of,
            first.nav,
            Decimal(0),
            None,
            Decimal(0) if first.nav is not None else None,
            initial_state,
            "MISSING_NAV" if first.nav is None else None,
        )
    ]
    cumulative = Decimal(1)
    cumulative_available = first.nav is not None
    for index, (start, end, flows) in enumerate(
        zip(snapshots[:-1], snapshots[1:], flows_by_period, strict=True), start=1
    ):
        missing_flow = any(flow.amount_in_base is None for flow in flows)
        flow_state = combine_analytics_states(tuple(flow.state for flow in flows)) if flows else AnalyticsState.COMPLETE
        flow_total = None if missing_flow else _decimal_sum(tuple(flow.amount_in_base or Decimal(0) for flow in flows))
        reason: str | None = None
        period_return: Decimal | None = None
        cumulative_return: Decimal | None = None
        if start.nav is None or end.nav is None:
            reason = "MISSING_NAV"
        elif missing_flow:
            reason = "MISSING_EXTERNAL_FLOW_VALUATION"
        elif start.nav == 0:
            reason = "ZERO_START_NAV"
        else:
            with localcontext() as context:
                context.prec = 200
                period_return = (end.nav - start.nav - (flow_total or Decimal(0))) / start.nav
                cumulative *= Decimal(1) + period_return
                cumulative_return = cumulative - Decimal(1)
        if period_return is None:
            cumulative_available = False
        point_state = PerformancePointState.UNAVAILABLE
        if period_return is not None:
            point_state = (
                PerformancePointState.STALE
                if AnalyticsState.STALE in {start.state, end.state, flow_state}
                else PerformancePointState.AVAILABLE
            )
        result.append(
            PerformancePoint(
                end.as_of,
                end.nav,
                flow_total,
                period_return,
                cumulative_return if cumulative_available else None,
                point_state,
                reason,
            )
        )
        if index == 1 and first.nav is None:
            cumulative_available = False
    return tuple(result)


def bounded_series_times(start_at: datetime, end_at: datetime, point_count: int) -> tuple[datetime, ...]:
    start = aware_utc(start_at)
    end = aware_utc(end_at)
    if end <= start:
        raise AnalyticsValidationError("performance end must follow start")
    if not 2 <= point_count <= 32:
        raise AnalyticsValidationError("performance point count must be between 2 and 32")
    if end - start > timedelta(days=366):
        raise AnalyticsValidationError("performance range cannot exceed 366 days")
    interval = (end - start) / (point_count - 1)
    return tuple(start + interval * index if index < point_count - 1 else end for index in range(point_count))
