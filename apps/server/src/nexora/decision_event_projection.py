from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from nexora.adapters.trd_bot.models import EventEnvelope, EventType, ResourceType, SourceReference

PROJECTION_SCHEMA_VERSION: Final = "nexora-decision-event-projection-v1"


class DecisionKind(StrEnum):
    CANDIDATE = "candidate"
    RISK_ASSESSMENT = "risk_assessment"
    PORTFOLIO_ASSESSMENT = "portfolio_assessment"
    MONITORING_ALERT = "monitoring_alert"


class LocalDecisionState(StrEnum):
    REVIEW_PENDING = "review_pending"


PROJECTED_RESOURCE_KINDS: Final = {
    ResourceType.MARKET_CONTEXT: DecisionKind.PORTFOLIO_ASSESSMENT,
    ResourceType.DECISION_EVALUATION: DecisionKind.PORTFOLIO_ASSESSMENT,
    ResourceType.CANDIDATE: DecisionKind.CANDIDATE,
    ResourceType.RISK_GATE: DecisionKind.RISK_ASSESSMENT,
    ResourceType.PORTFOLIO_INTELLIGENCE: DecisionKind.PORTFOLIO_ASSESSMENT,
    ResourceType.ALERT: DecisionKind.MONITORING_ALERT,
    ResourceType.ALERT_OUTCOME: DecisionKind.MONITORING_ALERT,
}
PROJECTED_RESOURCES: Final = tuple(PROJECTED_RESOURCE_KINDS)
SNAPSHOT_SCHEMA_ALLOWLIST: Final = {
    ResourceType.MARKET_CONTEXT: frozenset({"trd-bot-market-context-v1"}),
    ResourceType.DECISION_EVALUATION: frozenset({"trd-bot-decision-evaluation-v1"}),
    ResourceType.CANDIDATE: frozenset({"trd-bot-candidate-v1"}),
    ResourceType.RISK_GATE: frozenset({"trd-bot-risk-gate-v1"}),
    ResourceType.PORTFOLIO_INTELLIGENCE: frozenset({"trd-bot-portfolio-intelligence-v1"}),
    ResourceType.ALERT: frozenset({"trd-bot-alert-v1"}),
    ResourceType.ALERT_OUTCOME: frozenset({"trd-bot-alert-outcome-v1"}),
}
EVENT_SCHEMA_ALLOWLIST: Final = {
    EventType.MARKET_CONTEXT_ASSESSED: frozenset(
        {"market-context-assessed-v1", "trd-bot-market-context-assessed-event-v1"}
    ),
    EventType.DECISION_EVALUATION_COMPLETED: frozenset(
        {"decision-evaluation-completed-v1", "trd-bot-decision-evaluated-event-v1"}
    ),
    EventType.CANDIDATE_STATE_CHANGED: frozenset(
        {"candidate-state-changed-v1", "trd-bot-candidate-state-changed-event-v1"}
    ),
    EventType.RISK_GATE_COMPLETED: frozenset(
        {"risk-gate-completed-v1", "trd-bot-risk-gate-completed-event-v1"}
    ),
    EventType.PORTFOLIO_INTELLIGENCE_COMPLETED: frozenset(
        {"portfolio-intelligence-completed-v1", "trd-bot-portfolio-intelligence-event-v1"}
    ),
    EventType.ALERT_PUBLISHED: frozenset(
        {"alert-published-v1", "trd-bot-alert-published-event-v1"}
    ),
    EventType.ALERT_LIFECYCLE_CHANGED: frozenset(
        {"alert-lifecycle-changed-v1", "trd-bot-alert-lifecycle-event-v1"}
    ),
}
EVENT_RESOURCE_TYPES: Final = {
    EventType.MARKET_CONTEXT_ASSESSED: ResourceType.MARKET_CONTEXT,
    EventType.DECISION_EVALUATION_COMPLETED: ResourceType.DECISION_EVALUATION,
    EventType.CANDIDATE_STATE_CHANGED: ResourceType.CANDIDATE,
    EventType.RISK_GATE_COMPLETED: ResourceType.RISK_GATE,
    EventType.PORTFOLIO_INTELLIGENCE_COMPLETED: ResourceType.PORTFOLIO_INTELLIGENCE,
    EventType.ALERT_PUBLISHED: ResourceType.ALERT,
    EventType.ALERT_LIFECYCLE_CHANGED: ResourceType.ALERT,
}


def canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def source_reference_checksum(reference: SourceReference, payload: dict[str, Any]) -> str:
    evidence = {
        "observed_at": reference.observed_at.isoformat().replace("+00:00", "Z"),
        "payload": payload,
        "resource_id": reference.resource_id,
        "resource_schema_version": reference.resource_schema_version,
        "resource_type": reference.resource_type,
    }
    return "sha256:" + canonical_json_sha256(evidence)


class ProjectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProviderSnapshotItem(ProjectionModel):
    source_reference: SourceReference
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_checksum(self) -> ProviderSnapshotItem:
        if self.source_reference.checksum != source_reference_checksum(self.source_reference, self.payload):
            raise ValueError("source reference checksum mismatch")
        return self


class DecisionProjectionRecord(ProjectionModel):
    schema_version: Literal["nexora-decision-event-projection-v1"] = PROJECTION_SCHEMA_VERSION
    resource_type: ResourceType
    resource_id: str = Field(min_length=1, max_length=160)
    decision_kind: DecisionKind
    local_state: LocalDecisionState = LocalDecisionState.REVIEW_PENDING
    provider_release: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    source_schema_version: str = Field(min_length=1, max_length=160)
    source_observed_at: datetime
    source_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_event_id: str | None = Field(default=None, max_length=80)
    aggregate_type: str | None = Field(default=None, max_length=80)
    aggregate_id: str | None = Field(default=None, max_length=160)
    aggregate_version: int | None = Field(default=None, ge=1)
    payload: dict[str, Any]
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_record(self) -> DecisionProjectionRecord:
        if self.payload_sha256 != canonical_json_sha256(self.payload):
            raise ValueError("projection payload checksum mismatch")
        aggregate = (self.aggregate_type, self.aggregate_id, self.aggregate_version)
        if any(value is not None for value in aggregate) and any(value is None for value in aggregate):
            raise ValueError("aggregate lineage must be complete")
        return self


def _payload_identity(resource_type: ResourceType, payload: dict[str, Any]) -> str | None:
    for key in (
        f"{resource_type.value}_id",
        "assessment_id",
        "evaluation_id",
        "candidate_id",
        "alert_id",
        "outcome_id",
        "id",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def project_snapshot(
    resource_type: ResourceType, raw_item: dict[str, Any], *, provider_release: str
) -> DecisionProjectionRecord:
    if resource_type not in PROJECTED_RESOURCE_KINDS:
        raise ValueError("snapshot resource is not projected")
    try:
        item = ProviderSnapshotItem.model_validate(raw_item)
    except ValidationError as error:
        raise ValueError("invalid source-referenced snapshot item") from error
    reference = item.source_reference
    if reference.source_product != "trd_bot" or reference.source_version != provider_release:
        raise ValueError("snapshot provider lineage mismatch")
    if reference.resource_type != resource_type.value:
        raise ValueError("snapshot resource lineage mismatch")
    if reference.resource_schema_version not in SNAPSHOT_SCHEMA_ALLOWLIST[resource_type]:
        raise ValueError("unsupported snapshot schema")
    if item.payload.get("resource_schema_version") != reference.resource_schema_version:
        raise ValueError("snapshot payload schema lineage mismatch")
    identity = _payload_identity(resource_type, item.payload)
    if identity is not None and identity != reference.resource_id:
        raise ValueError("snapshot identity lineage mismatch")
    version = item.payload.get("aggregate_version")
    if version is not None and (not isinstance(version, int) or version < 1):
        raise ValueError("invalid snapshot aggregate version")
    return DecisionProjectionRecord(
        resource_type=resource_type,
        resource_id=reference.resource_id,
        decision_kind=PROJECTED_RESOURCE_KINDS[resource_type],
        provider_release=provider_release,
        source_schema_version=reference.resource_schema_version,
        source_observed_at=reference.observed_at,
        source_checksum=reference.checksum,
        aggregate_type=resource_type.value if version is not None else None,
        aggregate_id=reference.resource_id if version is not None else None,
        aggregate_version=version,
        payload=item.payload,
        payload_sha256=canonical_json_sha256(item.payload),
    )


def project_event(event: EventEnvelope, *, provider_release: str) -> DecisionProjectionRecord | None:
    resource_type = EVENT_RESOURCE_TYPES.get(event.event_type)
    if resource_type is None:
        return None
    if event.payload_schema not in EVENT_SCHEMA_ALLOWLIST[event.event_type]:
        raise ValueError("unsupported decision event payload schema")
    source = event.source
    if source.source_version != provider_release or source.resource_type != resource_type.value:
        raise ValueError("event provider or resource lineage mismatch")
    if source.resource_schema_version != event.payload_schema:
        raise ValueError("event schema lineage mismatch")
    if source.resource_id != event.aggregate.id or event.aggregate.type != resource_type.value:
        raise ValueError("event aggregate lineage mismatch")
    if source.checksum != source_reference_checksum(source, event.payload):
        raise ValueError("event source reference checksum mismatch")
    return DecisionProjectionRecord(
        resource_type=resource_type,
        resource_id=source.resource_id,
        decision_kind=PROJECTED_RESOURCE_KINDS[resource_type],
        provider_release=provider_release,
        source_schema_version=event.payload_schema,
        source_observed_at=event.occurred_at,
        source_checksum=source.checksum,
        source_event_id=event.event_id,
        aggregate_type=event.aggregate.type,
        aggregate_id=event.aggregate.id,
        aggregate_version=event.aggregate.version,
        payload=event.payload,
        payload_sha256=canonical_json_sha256(event.payload),
    )
