from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Final, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from nexora.adapters.postgresql.decision_projection import (
    ActiveDecisionProjection,
    DecisionEventProjectionRepository,
)
from nexora.adapters.trd_bot import ResourceType, TrdBotIntegrationMode
from nexora.decision_event_projection import DecisionProjectionRecord
from nexora.decision_feed import ProviderStatusResponse, provider_status
from nexora.risk_gate_explanation import ProviderRiskGatePayload

PORTFOLIO_IMPACT_SCHEMA_VERSION: Final = "nexora-portfolio-candidate-impact-v1"
EXPECTED_SCENARIO_SHOCKS: Final = (
    Decimal("-0.100000"),
    Decimal("-0.050000"),
    Decimal("0.050000"),
    Decimal("0.100000"),
)
EXPECTED_CHECK_NAMES: Final = (
    "portfolio_active",
    "portfolio_capacity",
    "projected_exposure",
    "projected_concentration",
    "candidate_correlation",
    "scenario_loss",
    "regime_alignment",
)


class PortfolioImpactError(RuntimeError):
    pass


class PortfolioImpactEvidenceNotFound(PortfolioImpactError):
    pass


class PortfolioImpactEvidenceInvalid(PortfolioImpactError):
    pass


class ImpactModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProviderStageOutcome(ImpactModel):
    schema_version: Literal["decision-stage-outcome-v1"]
    outcome_id: str = Field(min_length=1, max_length=160)
    evaluation_id: str = Field(min_length=1, max_length=160)
    stage: Literal["portfolio_simulation"]
    disposition: Literal["accepted", "rejected", "unavailable"]
    reason_codes: tuple[str, ...]
    evaluated_at: datetime
    offline_only: Literal[True]
    external_order_submission_allowed: Literal[False]
    outcome_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProviderPosition(ImpactModel):
    position_id: str = Field(min_length=1, max_length=160)
    pair: dict[str, str]
    side: Literal["long", "short"]
    notional: Decimal = Field(gt=0)
    unrealized_pnl: Decimal


class ProviderPortfolioSnapshot(ImpactModel):
    schema_version: Literal["decision-portfolio-snapshot-v1"]
    snapshot_id: str = Field(min_length=1, max_length=160)
    source: Literal["empty_baseline", "persisted_simulation"]
    portfolio_id: str | None = Field(default=None, max_length=160)
    mode: Literal["paper", "shadow"]
    dataset_id: str = Field(min_length=1, max_length=160)
    status: Literal["active"]
    as_of: datetime
    starting_equity: Decimal = Field(gt=0)
    cash: Decimal = Field(ge=0)
    equity: Decimal = Field(gt=0)
    open_positions: tuple[ProviderPosition, ...]
    snapshot_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_source_identity(self) -> Self:
        if (self.portfolio_id is None) != (self.source == "empty_baseline"):
            raise ValueError("portfolio snapshot source and identity are inconsistent")
        return self


class ProviderExposure(ImpactModel):
    current_gross_notional: Decimal = Field(ge=0)
    candidate_notional: Decimal = Field(gt=0)
    projected_gross_notional: Decimal = Field(gt=0)
    current_exposure_fraction: Decimal = Field(ge=0)
    projected_exposure_fraction: Decimal = Field(ge=0)
    projected_asset_concentration_fraction: Decimal = Field(ge=0)


class ProviderCorrelation(ImpactModel):
    status: Literal["available", "not_applicable", "unavailable"]
    maximum_absolute_correlation: Decimal | None = Field(default=None, ge=0, le=1)
    evidence: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_value(self) -> Self:
        if (self.maximum_absolute_correlation is None) == (self.status == "available"):
            raise ValueError("portfolio correlation status and value are inconsistent")
        return self


class ProviderScenario(ImpactModel):
    shock_fraction: Decimal = Field(ge=-1, le=1)
    existing_pnl: Decimal
    candidate_pnl: Decimal
    projected_equity: Decimal
    loss_fraction: Decimal = Field(ge=0)


class ProviderCheck(ImpactModel):
    name: str = Field(min_length=1, max_length=100)
    passed: bool
    actual_value: str = Field(min_length=1, max_length=100)
    limit_value: str = Field(min_length=1, max_length=100)
    explanation: str = Field(min_length=1, max_length=500)


class ProviderExitRecommendation(ImpactModel):
    position_id: str = Field(min_length=1, max_length=160)
    action: Literal["hold", "exit_risk", "exit_regime"]
    reason_codes: tuple[Literal["risk_limit", "regime_change"], ...]


class ProviderPortfolioAnalysis(ImpactModel):
    schema_version: Literal["decision-portfolio-analysis-v1"]
    analysis_id: str = Field(min_length=1, max_length=160)
    evaluation_id: str = Field(min_length=1, max_length=160)
    candidate_id: str = Field(min_length=1, max_length=160)
    snapshot: ProviderPortfolioSnapshot
    exposure: ProviderExposure
    correlation: ProviderCorrelation
    scenarios: tuple[ProviderScenario, ...]
    checks: tuple[ProviderCheck, ...]
    recommendation: Literal["accept", "reject"]
    exit_recommendations: tuple[ProviderExitRecommendation, ...]
    policy_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    analyzed_at: datetime
    offline_only: Literal[True]
    external_order_submission_allowed: Literal[False]
    analysis_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_bounded_analysis(self) -> Self:
        if tuple(item.shock_fraction for item in self.scenarios) != EXPECTED_SCENARIO_SHOCKS:
            raise ValueError("portfolio scenarios are incomplete or out of order")
        if tuple(item.name for item in self.checks) != EXPECTED_CHECK_NAMES:
            raise ValueError("portfolio checks are incomplete or out of order")
        expected = "accept" if all(item.passed for item in self.checks) else "reject"
        if self.recommendation != expected:
            raise ValueError("portfolio recommendation is inconsistent with its checks")
        return self


class ProviderPortfolioRecord(ImpactModel):
    schema_version: Literal["decision-portfolio-intelligence-record-v1"]
    evaluation_id: str = Field(min_length=1, max_length=160)
    outcome: ProviderStageOutcome
    risk_gate_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_version: str = Field(min_length=1, max_length=160)
    policy_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    recommendation: Literal["accept", "reject", "unavailable"]
    analysis: ProviderPortfolioAnalysis | None
    analyzed_at: datetime
    offline_only: Literal[True]
    external_order_submission_allowed: Literal[False]
    record_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProviderPortfolioPayload(ImpactModel):
    resource_schema_version: Literal["trd-bot-portfolio-intelligence-v1"]
    evaluation_id: str = Field(min_length=1, max_length=160)
    outcome_id: str = Field(min_length=1, max_length=160)
    record_schema_version: Literal["decision-portfolio-intelligence-record-v1"]
    risk_gate_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_version: str = Field(min_length=1, max_length=160)
    policy_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    disposition: Literal["accepted", "rejected", "unavailable"]
    recommendation: Literal["accept", "reject", "unavailable"]
    has_analysis: bool
    snapshot_id: str | None = Field(default=None, max_length=160)
    candidate_id: str | None = Field(default=None, max_length=160)
    analyzed_at: datetime
    offline_only: Literal[True]
    external_order_submission_allowed: Literal[False]
    record_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    record: ProviderPortfolioRecord

    @model_validator(mode="after")
    def validate_lineage(self) -> Self:
        record = self.record
        analysis = record.analysis
        consistent = (
            self.evaluation_id == record.evaluation_id == record.outcome.evaluation_id
            and self.outcome_id == record.outcome.outcome_id
            and self.risk_gate_checksum == record.risk_gate_checksum
            and self.policy_version == record.policy_version
            and self.policy_checksum == record.policy_checksum
            and self.disposition == record.outcome.disposition
            and self.recommendation == record.recommendation
            and self.analyzed_at == record.analyzed_at == record.outcome.evaluated_at
            and self.record_checksum == record.record_checksum
            and self.has_analysis == (analysis is not None)
        )
        if not consistent:
            raise ValueError("portfolio intelligence lineage is inconsistent")
        if analysis is None:
            if (
                self.recommendation != "unavailable"
                or self.disposition != "unavailable"
                or self.snapshot_id is not None
                or self.candidate_id is not None
                or record.outcome.reason_codes != ("portfolio_unavailable",)
            ):
                raise ValueError("unavailable portfolio intelligence is inconsistent")
            return self
        expected_disposition = "accepted" if analysis.recommendation == "accept" else "rejected"
        expected_reasons = () if expected_disposition == "accepted" else ("portfolio_policy_rejected",)
        if (
            analysis.evaluation_id != self.evaluation_id
            or analysis.policy_checksum != self.policy_checksum
            or analysis.analyzed_at != self.analyzed_at
            or self.snapshot_id != analysis.snapshot.snapshot_id
            or self.candidate_id != analysis.candidate_id
            or self.recommendation != analysis.recommendation
            or self.disposition != expected_disposition
            or record.outcome.reason_codes != expected_reasons
        ):
            raise ValueError("portfolio analysis lineage is inconsistent")
        return self


class PortfolioPolicyResponse(ImpactModel):
    version: str
    checksum: str


class ProviderReasonResponse(ImpactModel):
    namespace: Literal["trd_bot"] = "trd_bot"
    code: str


class PortfolioUncertaintyResponse(ImpactModel):
    state: Literal["not_supplied"] = "not_supplied"
    value: None = None
    reason_code: Literal["TRD_BOT_PORTFOLIO_UNCERTAINTY_NOT_SUPPLIED"] = "TRD_BOT_PORTFOLIO_UNCERTAINTY_NOT_SUPPLIED"


class PortfolioSourceResponse(ImpactModel):
    schema_version: Literal["nexora-source-reference-v1"] = "nexora-source-reference-v1"
    source_product: Literal["trd_bot"] = "trd_bot"
    source_version: str
    resource_type: Literal["portfolio_intelligence"] = "portfolio_intelligence"
    resource_id: str
    resource_schema_version: Literal["trd-bot-portfolio-intelligence-v1"]
    observed_at: datetime
    checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    event_id: str | None = None
    aggregate_type: str | None = None
    aggregate_id: str | None = None
    aggregate_version: int | None = Field(default=None, ge=1)


class PortfolioImpactResponse(ImpactModel):
    evaluation_id: str
    recommendation: Literal["accept", "reject", "unavailable"]
    disposition: Literal["accepted", "rejected", "unavailable"]
    candidate_id: str | None
    snapshot_id: str | None
    policy: PortfolioPolicyResponse
    provider_reason_codes: tuple[ProviderReasonResponse, ...]
    analysis: ProviderPortfolioAnalysis | None
    uncertainty: PortfolioUncertaintyResponse
    analyzed_at: datetime
    source: PortfolioSourceResponse
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    risk_gate_checksum_cross_validated: Literal[True] = True
    advisory_only: Literal[True] = True
    transaction_created: Literal[False] = False
    order_intent_created: Literal[False] = False
    external_order_submission_allowed: Literal[False] = False


class PortfolioImpactDetailResponse(ImpactModel):
    schema_version: Literal["nexora-portfolio-candidate-impact-v1"] = PORTFOLIO_IMPACT_SCHEMA_VERSION
    provider: ProviderStatusResponse
    portfolio_impact: PortfolioImpactResponse | None


def _projection_records(snapshot: ActiveDecisionProjection) -> list[DecisionProjectionRecord] | None:
    try:
        records = [DecisionProjectionRecord.model_validate(raw) for raw in snapshot.projection.values()]
    except ValidationError:
        return None
    if any(record.provider_release != snapshot.provider_version for record in records):
        return None
    return records


def _validated_risk_gate(records: list[DecisionProjectionRecord], evaluation_id: str) -> ProviderRiskGatePayload:
    record = next(
        (
            item
            for item in records
            if item.resource_type is ResourceType.RISK_GATE and item.resource_id == evaluation_id
        ),
        None,
    )
    if record is None:
        raise PortfolioImpactEvidenceInvalid("matching risk gate evidence is unavailable")
    try:
        return ProviderRiskGatePayload.model_validate(record.payload)
    except ValidationError as error:
        raise PortfolioImpactEvidenceInvalid("matching risk gate evidence is invalid") from error


def _impact(record: DecisionProjectionRecord, records: list[DecisionProjectionRecord]) -> PortfolioImpactResponse:
    try:
        payload = ProviderPortfolioPayload.model_validate(record.payload)
    except ValidationError as error:
        raise PortfolioImpactEvidenceInvalid("portfolio impact evidence is invalid") from error
    risk_gate = _validated_risk_gate(records, payload.evaluation_id)
    if risk_gate.decision != "approved" or risk_gate.record_checksum != payload.risk_gate_checksum:
        raise PortfolioImpactEvidenceInvalid("portfolio impact risk lineage is invalid")
    return PortfolioImpactResponse(
        evaluation_id=payload.evaluation_id,
        recommendation=payload.recommendation,
        disposition=payload.disposition,
        candidate_id=payload.candidate_id,
        snapshot_id=payload.snapshot_id,
        policy=PortfolioPolicyResponse(version=payload.policy_version, checksum=payload.policy_checksum),
        provider_reason_codes=tuple(ProviderReasonResponse(code=code) for code in payload.record.outcome.reason_codes),
        analysis=payload.record.analysis,
        uncertainty=PortfolioUncertaintyResponse(),
        analyzed_at=payload.analyzed_at,
        source=PortfolioSourceResponse(
            source_version=record.provider_release,
            resource_id=record.resource_id,
            resource_schema_version="trd-bot-portfolio-intelligence-v1",
            observed_at=record.source_observed_at,
            checksum=record.source_checksum,
            event_id=record.source_event_id,
            aggregate_type=record.aggregate_type,
            aggregate_id=record.aggregate_id,
            aggregate_version=record.aggregate_version,
        ),
        evidence_sha256=record.payload_sha256,
    )


class PortfolioCandidateImpactService:
    def __init__(
        self,
        repository: DecisionEventProjectionRepository,
        integration_mode: TrdBotIntegrationMode | None,
    ) -> None:
        self._repository = repository
        self._integration_mode = integration_mode

    def detail(self, owner_id: UUID, evaluation_id: str) -> PortfolioImpactDetailResponse:
        snapshot = self._repository.active_snapshot(owner_id)
        records = None if snapshot is None else _projection_records(snapshot)
        status = provider_status(
            self._integration_mode,
            snapshot,
            invalid=snapshot is not None and records is None,
        )
        if snapshot is None or records is None:
            return PortfolioImpactDetailResponse(provider=status, portfolio_impact=None)
        record = next(
            (
                item
                for item in records
                if item.resource_type is ResourceType.PORTFOLIO_INTELLIGENCE and item.resource_id == evaluation_id
            ),
            None,
        )
        if record is None:
            raise PortfolioImpactEvidenceNotFound("portfolio impact evidence is unavailable")
        return PortfolioImpactDetailResponse(
            provider=status,
            portfolio_impact=_impact(record, records),
        )
