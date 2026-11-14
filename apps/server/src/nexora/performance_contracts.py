from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from nexora.holdings_projection import BasisStatus, CostBasisMethod
from nexora.performance import AnalyticsState, PerformancePointState
from nexora.valuation import ValuationEvidenceKind, ValuationEvidenceState


class PerformanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PositionValuationResponse(PerformanceModel):
    schema_version: Literal["nexora-position-valuation-v1"] = "nexora-position-valuation-v1"
    account_id: UUID
    asset_id: UUID
    quantity: str
    state: ValuationEvidenceState
    evidence_kind: ValuationEvidenceKind
    unit_value: str | None
    evidence_ids: list[UUID]
    evidence_at: datetime | None
    valid_until: datetime | None
    source_references: list[str]
    market_value: str | None
    basis_status: BasisStatus
    cost_basis_asset_id: UUID | None
    cost_basis: str | None
    cost_basis_in_base: str | None
    unrealized_pnl: str | None


class RealizedPnlEventResponse(PerformanceModel):
    schema_version: Literal["nexora-realized-pnl-event-v1"] = "nexora-realized-pnl-event-v1"
    transaction_id: UUID
    occurred_at: datetime
    proceeds_in_base: str | None
    cost_basis_in_base: str | None
    realized_pnl: str | None
    state: AnalyticsState
    reason_code: str | None


class PortfolioAnalyticsResponse(PerformanceModel):
    schema_version: Literal["nexora-portfolio-analytics-v1"] = "nexora-portfolio-analytics-v1"
    portfolio_id: UUID
    base_asset_id: UUID
    as_of: datetime
    cost_basis_method: CostBasisMethod
    policy_version: str
    journal_sha256: str
    journal_transaction_count: int
    state: AnalyticsState
    nav: str | None
    priced_value: str
    realized_pnl: str | None
    unrealized_pnl: str | None
    positions: list[PositionValuationResponse]
    realized_events: list[RealizedPnlEventResponse]


class PerformancePointResponse(PerformanceModel):
    schema_version: Literal["nexora-performance-point-v1"] = "nexora-performance-point-v1"
    as_of: datetime
    nav: str | None
    external_flow: str | None
    period_return: str | None
    cumulative_return: str | None
    state: PerformancePointState
    reason_code: str | None


class PerformanceSeriesResponse(PerformanceModel):
    schema_version: Literal["nexora-performance-series-v1"] = "nexora-performance-series-v1"
    portfolio_id: UUID
    base_asset_id: UUID
    cost_basis_method: CostBasisMethod
    policy_version: str
    start_at: datetime
    end_at: datetime
    points: list[PerformancePointResponse]
