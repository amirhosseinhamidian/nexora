from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Sha256Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
PlainSha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware UTC")
    return value


def _require_optional_utc(value: datetime | None) -> datetime | None:
    return None if value is None else _require_utc(value)


class ResourceType(StrEnum):
    MARKET_CONTEXT = "market_context"
    DECISION_EVALUATION = "decision_evaluation"
    CANDIDATE = "candidate"
    RISK_GATE = "risk_gate"
    PORTFOLIO_INTELLIGENCE = "portfolio_intelligence"
    ALERT = "alert"
    ALERT_OUTCOME = "alert_outcome"
    PAPER_SHADOW_PORTFOLIO = "paper_shadow_portfolio"
    PAPER_SHADOW_POSITION = "paper_shadow_position"
    SIMULATION_OUTCOME = "simulation_outcome"


class CommandType(StrEnum):
    ACCEPT = "decision_review.accept.v1"
    REJECT = "decision_review.reject.v1"
    DEFER = "decision_review.defer.v1"


class CapabilitiesResponse(ContractModel):
    schema_version: Literal["nexora-integration-capabilities-v1"]
    provider: Literal["trd_bot"]
    provider_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    contract_versions: tuple[str, ...]
    event_envelopes: tuple[str, ...]
    export_manifests: tuple[str, ...]
    source_references: tuple[str, ...]
    commands: tuple[str, ...]
    generated_at: datetime

    _generated_at_is_utc = field_validator("generated_at")(_require_utc)


class SourceReference(ContractModel):
    schema_version: Literal["nexora-source-reference-v1"]
    source_product: Literal["trd_bot"]
    source_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=160)
    resource_schema_version: str = Field(min_length=1, max_length=120)
    observed_at: datetime
    checksum: Sha256Digest

    _observed_at_is_utc = field_validator("observed_at")(_require_utc)


class SnapshotPage(ContractModel):
    schema_version: Literal["nexora-source-snapshot-page-v1"]
    items: tuple[dict[str, Any], ...]
    next_cursor: str | None
    has_more: bool

    @model_validator(mode="after")
    def validate_cursor(self) -> SnapshotPage:
        if self.has_more and not self.next_cursor:
            raise ValueError("a continuing snapshot page requires next_cursor")
        return self


class AggregateReference(ContractModel):
    type: str = Field(min_length=1, max_length=80)
    id: str = Field(min_length=1, max_length=160)
    version: int = Field(ge=1)


class EventType(StrEnum):
    MARKET_CONTEXT_ASSESSED = "market_context.assessed.v1"
    DECISION_EVALUATION_COMPLETED = "decision.evaluation.completed.v1"
    CANDIDATE_STATE_CHANGED = "candidate.state.changed.v1"
    RISK_GATE_COMPLETED = "risk_gate.completed.v1"
    PORTFOLIO_INTELLIGENCE_COMPLETED = "portfolio_intelligence.completed.v1"
    ALERT_PUBLISHED = "alert.published.v1"
    ALERT_LIFECYCLE_CHANGED = "alert.lifecycle.changed.v1"
    SIMULATION_POSITION_OPENED = "simulation.position.opened.v1"
    SIMULATION_POSITION_UPDATED = "simulation.position.updated.v1"
    SIMULATION_POSITION_CLOSED = "simulation.position.closed.v1"
    OUTCOME_RECORDED = "outcome.recorded.v1"


class EventEnvelope(ContractModel):
    schema_version: Literal["trd-integration-event-envelope-v1"]
    event_id: str = Field(pattern=r"^evt_[A-Za-z0-9_-]{16,64}$")
    event_type: EventType
    occurred_at: datetime
    emitted_at: datetime
    source: SourceReference
    aggregate: AggregateReference
    correlation_id: UUID
    causation_id: UUID | None
    idempotency_key: str = Field(min_length=16, max_length=160)
    payload_schema: str = Field(min_length=1, max_length=160)
    payload: dict[str, Any]
    payload_checksum: Sha256Digest

    _occurred_at_is_utc = field_validator("occurred_at")(_require_utc)
    _emitted_at_is_utc = field_validator("emitted_at")(_require_utc)

    @model_validator(mode="after")
    def validate_payload_checksum(self) -> EventEnvelope:
        encoded = json.dumps(self.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
        if self.payload_checksum != expected:
            raise ValueError("payload checksum mismatch")
        return self


class EventPage(ContractModel):
    schema_version: Literal["trd-integration-event-page-v1"]
    events: tuple[EventEnvelope, ...]
    next_cursor: str | None
    has_more: bool

    @model_validator(mode="after")
    def validate_cursor(self) -> EventPage:
        if self.has_more and not self.next_cursor:
            raise ValueError("a continuing event page requires next_cursor")
        return self


class DecisionReviewCommand(ContractModel):
    schema_version: Literal["nexora-decision-review-command-v1"] = "nexora-decision-review-command-v1"
    command_type: CommandType
    decision_id: str = Field(min_length=1)
    portfolio_mode: Literal["paper", "shadow"]
    reviewed_at: datetime
    reason: str = Field(min_length=1, max_length=1000)
    evidence: SourceReference

    _reviewed_at_is_utc = field_validator("reviewed_at")(_require_utc)


class CommandReceipt(ContractModel):
    schema_version: Literal["nexora-command-receipt-v1"]
    command_id: str = Field(min_length=1)
    command_type: CommandType
    status: Literal["accepted", "duplicate"]
    idempotency_key: str = Field(min_length=16, max_length=160)
    correlation_id: UUID
    accepted_at: datetime

    _accepted_at_is_utc = field_validator("accepted_at")(_require_utc)


class ExportRequest(ContractModel):
    schema_version: Literal["nexora-export-request-v1"] = "nexora-export-request-v1"
    mode: Literal["full", "incremental", "selected"]
    formats: tuple[Literal["json", "jsonl", "csv", "parquet", "zip_bundle"], ...] = Field(min_length=1)
    profile: Literal["private", "ai_safe"]
    scope: tuple[ResourceType, ...] = Field(min_length=1)
    filters: dict[str, Any]

    @model_validator(mode="after")
    def validate_unique_values(self) -> ExportRequest:
        if len(set(self.formats)) != len(self.formats) or len(set(self.scope)) != len(self.scope):
            raise ValueError("export formats and scope must be unique")
        return self


class ExportStatus(ContractModel):
    schema_version: Literal["nexora-export-status-v1"]
    export_id: str = Field(pattern=r"^exp_[A-Za-z0-9_-]{16,64}$")
    status: Literal["accepted", "running", "complete", "failed"]
    requested_at: datetime
    completed_at: datetime | None = None

    _requested_at_is_utc = field_validator("requested_at")(_require_utc)
    _completed_at_is_utc = field_validator("completed_at")(_require_optional_utc)


class CurrencyUnitContext(ContractModel):
    base_currency: str = Field(pattern=r"^[A-Z0-9]{2,12}$")
    quantity_units_explicit: Literal[True]


class ExportFile(ContractModel):
    path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    row_count: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    sha256: PlainSha256Digest
    schema_version: str = Field(min_length=1)


class ExportManifest(ContractModel):
    schema_version: Literal["nexora-export-manifest-v1"]
    export_id: str = Field(pattern=r"^exp_[A-Za-z0-9_-]{16,64}$")
    generated_at: datetime
    mode: Literal["full", "incremental", "selected"]
    profile: Literal["private", "ai_safe"]
    source_versions: dict[str, str]
    scope: tuple[str, ...] = Field(min_length=1)
    filters: dict[str, Any]
    timezone: Literal["UTC"]
    currency_unit_context: CurrencyUnitContext
    lineage_references: tuple[SourceReference, ...]
    files: tuple[ExportFile, ...] = Field(min_length=1)
    redaction_profile: str = Field(min_length=1)
    completion_status: Literal["complete"]

    _generated_at_is_utc = field_validator("generated_at")(_require_utc)

    @model_validator(mode="after")
    def validate_collections(self) -> ExportManifest:
        if not self.source_versions or any(not key or not value for key, value in self.source_versions.items()):
            raise ValueError("source versions must be non-empty")
        if len(set(self.scope)) != len(self.scope):
            raise ValueError("export scope must be unique")
        return self


class IntegrationErrorDetail(ContractModel):
    code: Literal[
        "INVALID_REQUEST",
        "UNAUTHORIZED",
        "FORBIDDEN",
        "NOT_FOUND",
        "IDEMPOTENCY_CONFLICT",
        "CURSOR_EXPIRED",
        "INCOMPATIBLE_CONTRACT",
        "UNSUPPORTED_SCHEMA",
        "CHECKSUM_MISMATCH",
        "SOURCE_UNAVAILABLE",
    ]
    message: str = Field(min_length=1, max_length=500)
    retryable: bool
    details: dict[str, Any]


class IntegrationErrorEnvelope(ContractModel):
    schema_version: Literal["nexora-integration-error-v1"]
    correlation_id: UUID
    occurred_at: datetime
    error: IntegrationErrorDetail

    _occurred_at_is_utc = field_validator("occurred_at")(_require_utc)
