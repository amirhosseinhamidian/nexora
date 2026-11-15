from __future__ import annotations

from datetime import datetime
from typing import Any, Final, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from nexora.adapters.postgresql.decision_projection import (
    ActiveDecisionProjection,
    DecisionEventProjectionRepository,
)
from nexora.adapters.trd_bot import ResourceType, TrdBotIntegrationMode
from nexora.decision_event_projection import DecisionProjectionRecord
from nexora.decision_feed import ProviderStatusResponse, provider_status

RISK_GATE_EXPLANATION_SCHEMA_VERSION: Final = "nexora-risk-gate-explanation-v1"
EXPECTED_RISK_CHECK_NAMES: Final = (
    "candidate_fresh",
    "ranking_score",
    "reward_risk",
    "risk_budget",
    "notional_cap",
)


class RiskGateExplanationError(RuntimeError):
    pass


class RiskGateEvidenceNotFound(RiskGateExplanationError):
    pass


class RiskGateEvidenceInvalid(RiskGateExplanationError):
    pass


class RiskModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProviderRiskCheck(RiskModel):
    name: str = Field(min_length=1, max_length=100)
    passed: bool
    actual_value: str = Field(min_length=1, max_length=100)
    limit_value: str = Field(min_length=1, max_length=100)
    explanation: str = Field(min_length=1, max_length=500)


class ProviderStageOutcome(RiskModel):
    schema_version: Literal["decision-stage-outcome-v1"]
    outcome_id: str = Field(min_length=1, max_length=160)
    evaluation_id: str = Field(min_length=1, max_length=160)
    stage: Literal["risk_gate"]
    disposition: Literal["accepted", "rejected"]
    reason_codes: tuple[str, ...]
    evaluated_at: datetime
    offline_only: Literal[True]
    external_order_submission_allowed: Literal[False]
    outcome_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProviderRiskAssessment(RiskModel):
    schema_version: Literal["decision-risk-assessment-v1"]
    assessment_id: str = Field(min_length=1, max_length=160)
    evaluation_id: str = Field(min_length=1, max_length=160)
    candidate_id: str = Field(min_length=1, max_length=160)
    candidate_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    rank: int = Field(ge=1)
    ranking_score: str = Field(min_length=1, max_length=100)
    decision: Literal["approved", "rejected"]
    checks: tuple[ProviderRiskCheck, ...] = Field(min_length=1)
    position_sizing: dict[str, Any] | None
    evaluated_at: datetime
    policy_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    offline_only: Literal[True]
    external_order_submission_allowed: Literal[False]
    assessment_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_provider_decision(self) -> Self:
        check_names = tuple(check.name for check in self.checks)
        if check_names != EXPECTED_RISK_CHECK_NAMES:
            raise ValueError("risk assessment checks are incomplete or out of order")
        expected_decision = "approved" if all(check.passed for check in self.checks) else "rejected"
        if self.decision != expected_decision:
            raise ValueError("risk assessment decision is inconsistent with its checks")
        if (self.position_sizing is not None) != (self.decision == "approved"):
            raise ValueError("risk assessment position sizing is inconsistent with its decision")
        return self


class ProviderRiskGateRecord(RiskModel):
    schema_version: Literal["decision-risk-gate-record-v1"]
    evaluation_id: str = Field(min_length=1, max_length=160)
    outcome: ProviderStageOutcome
    candidate_ranking_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_version: str = Field(min_length=1, max_length=160)
    policy_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    assessment: ProviderRiskAssessment
    approved_candidate_id: str | None = Field(default=None, max_length=160)
    evaluated_at: datetime
    offline_only: Literal[True]
    external_order_submission_allowed: Literal[False]
    record_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProviderRiskGatePayload(RiskModel):
    resource_schema_version: Literal["trd-bot-risk-gate-v1"]
    evaluation_id: str = Field(min_length=1, max_length=160)
    outcome_id: str = Field(min_length=1, max_length=160)
    record_schema_version: Literal["decision-risk-gate-record-v1"]
    candidate_ranking_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_version: str = Field(min_length=1, max_length=160)
    policy_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    disposition: Literal["accepted", "rejected"]
    decision: Literal["approved", "rejected"]
    assessment_id: str = Field(min_length=1, max_length=160)
    assessment_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_candidate_id: str | None = Field(default=None, max_length=160)
    has_position_sizing: bool
    evaluated_at: datetime
    offline_only: Literal[True]
    external_order_submission_allowed: Literal[False]
    record_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    record: ProviderRiskGateRecord

    @model_validator(mode="after")
    def validate_lineage(self) -> Self:
        record = self.record
        assessment = record.assessment
        outcome = record.outcome
        consistent = (
            self.evaluation_id == record.evaluation_id == assessment.evaluation_id == outcome.evaluation_id
            and self.outcome_id == outcome.outcome_id
            and self.candidate_ranking_checksum == record.candidate_ranking_checksum
            and self.policy_version == record.policy_version
            and self.policy_checksum == record.policy_checksum == assessment.policy_checksum
            and self.disposition == outcome.disposition
            and self.decision == assessment.decision
            and self.assessment_id == assessment.assessment_id
            and self.assessment_checksum == assessment.assessment_checksum
            and self.approved_candidate_id == record.approved_candidate_id
            and self.evaluated_at == record.evaluated_at == assessment.evaluated_at == outcome.evaluated_at
            and self.record_checksum == record.record_checksum
            and self.has_position_sizing == (assessment.position_sizing is not None)
        )
        expected_disposition = "accepted" if self.decision == "approved" else "rejected"
        expected_candidate = assessment.candidate_id if self.decision == "approved" else None
        expected_reason_codes = () if self.decision == "approved" else ("risk_policy_rejected",)
        if not consistent or self.disposition != expected_disposition:
            raise ValueError("risk gate lineage is inconsistent")
        if self.approved_candidate_id != expected_candidate:
            raise ValueError("risk gate approved candidate is inconsistent")
        if outcome.reason_codes != expected_reason_codes:
            raise ValueError("risk gate reason codes are inconsistent")
        return self


class RiskPolicyResponse(RiskModel):
    version: str
    checksum: str


class ProviderReasonCodeResponse(RiskModel):
    namespace: Literal["trd_bot"] = "trd_bot"
    code: str = Field(min_length=1, max_length=160)


class RiskCheckResponse(RiskModel):
    name: str
    passed: bool
    actual_value: str
    limit_value: str
    explanation: str


class RiskUncertaintyResponse(RiskModel):
    state: Literal["not_supplied"] = "not_supplied"
    value: None = None
    reason_code: Literal["TRD_BOT_RISK_UNCERTAINTY_NOT_SUPPLIED"] = "TRD_BOT_RISK_UNCERTAINTY_NOT_SUPPLIED"


class RiskSourceReferenceResponse(RiskModel):
    schema_version: Literal["nexora-source-reference-v1"] = "nexora-source-reference-v1"
    source_product: Literal["trd_bot"] = "trd_bot"
    source_version: str
    resource_type: Literal["risk_gate"] = "risk_gate"
    resource_id: str
    resource_schema_version: Literal["trd-bot-risk-gate-v1"]
    observed_at: datetime
    checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    event_id: str | None = None
    aggregate_type: str | None = None
    aggregate_id: str | None = None
    aggregate_version: int | None = Field(default=None, ge=1)


class RiskGateExplanationResponse(RiskModel):
    evaluation_id: str
    decision: Literal["approved", "rejected"]
    disposition: Literal["accepted", "rejected"]
    candidate_id: str
    approved_candidate_id: str | None
    policy: RiskPolicyResponse
    provider_reason_codes: tuple[ProviderReasonCodeResponse, ...]
    checks: tuple[RiskCheckResponse, ...]
    uncertainty: RiskUncertaintyResponse
    evaluated_at: datetime
    source: RiskSourceReferenceResponse
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    position_sizing_exposed: Literal[False] = False
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False


class RiskGateDetailResponse(RiskModel):
    schema_version: Literal["nexora-risk-gate-explanation-v1"] = RISK_GATE_EXPLANATION_SCHEMA_VERSION
    provider: ProviderStatusResponse
    risk_gate: RiskGateExplanationResponse | None


def _projection_records(snapshot: ActiveDecisionProjection) -> list[DecisionProjectionRecord] | None:
    try:
        records = [DecisionProjectionRecord.model_validate(raw) for raw in snapshot.projection.values()]
    except ValidationError:
        return None
    if any(record.provider_release != snapshot.provider_version for record in records):
        return None
    return records


def _explanation(record: DecisionProjectionRecord) -> RiskGateExplanationResponse:
    try:
        payload = ProviderRiskGatePayload.model_validate(record.payload)
    except ValidationError as error:
        raise RiskGateEvidenceInvalid("risk gate evidence is invalid") from error
    assessment = payload.record.assessment
    return RiskGateExplanationResponse(
        evaluation_id=payload.evaluation_id,
        decision=payload.decision,
        disposition=payload.disposition,
        candidate_id=assessment.candidate_id,
        approved_candidate_id=payload.approved_candidate_id,
        policy=RiskPolicyResponse(version=payload.policy_version, checksum=payload.policy_checksum),
        provider_reason_codes=tuple(
            ProviderReasonCodeResponse(code=code) for code in payload.record.outcome.reason_codes
        ),
        checks=tuple(RiskCheckResponse.model_validate(check.model_dump()) for check in assessment.checks),
        uncertainty=RiskUncertaintyResponse(),
        evaluated_at=payload.evaluated_at,
        source=RiskSourceReferenceResponse(
            source_version=record.provider_release,
            resource_id=record.resource_id,
            resource_schema_version="trd-bot-risk-gate-v1",
            observed_at=record.source_observed_at,
            checksum=record.source_checksum,
            event_id=record.source_event_id,
            aggregate_type=record.aggregate_type,
            aggregate_id=record.aggregate_id,
            aggregate_version=record.aggregate_version,
        ),
        evidence_sha256=record.payload_sha256,
    )


class RiskGateExplanationService:
    def __init__(
        self,
        repository: DecisionEventProjectionRepository,
        integration_mode: TrdBotIntegrationMode | None,
    ) -> None:
        self._repository = repository
        self._integration_mode = integration_mode

    def detail(self, owner_id: UUID, evaluation_id: str) -> RiskGateDetailResponse:
        snapshot = self._repository.active_snapshot(owner_id)
        records = None if snapshot is None else _projection_records(snapshot)
        status = provider_status(
            self._integration_mode,
            snapshot,
            invalid=snapshot is not None and records is None,
        )
        if snapshot is None or records is None:
            return RiskGateDetailResponse(provider=status, risk_gate=None)
        record = next(
            (
                item
                for item in records
                if item.resource_type is ResourceType.RISK_GATE and item.resource_id == evaluation_id
            ),
            None,
        )
        if record is None:
            raise RiskGateEvidenceNotFound("risk gate evidence is unavailable")
        return RiskGateDetailResponse(provider=status, risk_gate=_explanation(record))
