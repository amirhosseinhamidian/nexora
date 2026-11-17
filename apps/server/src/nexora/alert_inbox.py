from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Final, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from nexora.adapters.postgresql.alert_inbox import (
    AlertInboxRepository,
    AlertInboxRepositoryConflict,
    AlertStateView,
    AlertStateWrite,
)
from nexora.adapters.postgresql.decision_projection import (
    ActiveDecisionProjection,
    DecisionEventProjectionRepository,
)
from nexora.adapters.trd_bot import ResourceType, TrdBotIntegrationMode
from nexora.decision_event_projection import DecisionProjectionRecord
from nexora.decision_feed import ProviderStatusResponse, provider_status

ALERT_INBOX_SCHEMA_VERSION: Final = "nexora-alert-inbox-v1"
ALERT_REASON_CODES: Final = {
    "acknowledge": "owner.alert.acknowledged",
    "snooze": "owner.alert.snoozed",
}


class AlertInboxError(RuntimeError):
    pass


class AlertInboxNotFound(AlertInboxError):
    pass


class AlertInboxConflict(AlertInboxError):
    pass


class AlertInboxValidationError(AlertInboxError):
    pass


class AlertAction(StrEnum):
    ACKNOWLEDGE = "acknowledge"
    SNOOZE = "snooze"


class AlertState(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    SNOOZED = "snoozed"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class AlertModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


class CreateAlertTransitionRequest(AlertModel):
    action: AlertAction
    occurred_at: datetime
    snooze_until: datetime | None = None
    expected_version: int = Field(ge=0)
    evidence_generation: int = Field(ge=1)
    source_evidence_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    _occurred_at_utc = field_validator("occurred_at")(_utc)
    _snooze_until_utc = field_validator("snooze_until")(lambda value: None if value is None else _utc(value))

    @model_validator(mode="after")
    def validate_transition(self) -> Self:
        if self.occurred_at > datetime.now(UTC):
            raise ValueError("occurred_at must not be in the future")
        if self.action is AlertAction.SNOOZE:
            if self.snooze_until is None:
                raise ValueError("snooze requires snooze_until")
            if self.snooze_until <= datetime.now(UTC):
                raise ValueError("snooze_until must be in the future")
        elif self.snooze_until is not None:
            raise ValueError("only snooze may include snooze_until")
        return self


class AlertSourceReferenceResponse(AlertModel):
    schema_version: Literal["nexora-source-reference-v1"] = "nexora-source-reference-v1"
    source_product: Literal["trd_bot"] = "trd_bot"
    source_version: str
    resource_type: Literal["alert"] = "alert"
    resource_id: str
    resource_schema_version: str
    observed_at: datetime
    checksum: str
    event_id: str | None = None
    aggregate_type: str | None = None
    aggregate_id: str | None = None
    aggregate_version: int | None = None


class AlertStateHistoryResponse(AlertModel):
    alert_history_id: UUID
    state_version: int = Field(ge=1)
    state: AlertState
    reason_code: str
    snooze_until: datetime | None
    evidence_generation: int = Field(ge=1)
    source_evidence_checksum: str
    occurred_at: datetime
    recorded_at: datetime


class AlertInboxItemResponse(AlertModel):
    alert_id: str
    local_state: AlertState
    current_version: int = Field(ge=0)
    snooze_until: datetime | None = None
    source: AlertSourceReferenceResponse
    evidence: dict[str, Any]
    evidence_sha256: str
    history: tuple[AlertStateHistoryResponse, ...]


class AlertInboxResponse(AlertModel):
    schema_version: Literal["nexora-alert-inbox-v1"] = ALERT_INBOX_SCHEMA_VERSION
    provider: ProviderStatusResponse
    items: tuple[AlertInboxItemResponse, ...]
    notification_delivery_enabled: Literal[False] = False


def _history_response(view: AlertStateView) -> AlertStateHistoryResponse:
    return AlertStateHistoryResponse(
        alert_history_id=view.alert_history_id,
        state_version=view.state_version,
        state=AlertState(view.state),
        reason_code=view.reason_code,
        snooze_until=view.snooze_until,
        evidence_generation=view.evidence_generation,
        source_evidence_checksum=view.source_evidence_checksum,
        occurred_at=view.occurred_at,
        recorded_at=view.recorded_at,
    )


def _source(record: DecisionProjectionRecord) -> AlertSourceReferenceResponse:
    return AlertSourceReferenceResponse(
        source_version=record.provider_release,
        resource_id=record.resource_id,
        resource_schema_version=record.source_schema_version,
        observed_at=record.source_observed_at,
        checksum=record.source_checksum,
        event_id=record.source_event_id,
        aggregate_type=record.aggregate_type,
        aggregate_id=record.aggregate_id,
        aggregate_version=record.aggregate_version,
    )


def _visible_alerts(snapshot: ActiveDecisionProjection) -> list[DecisionProjectionRecord] | None:
    records: list[DecisionProjectionRecord] = []
    try:
        for raw in snapshot.projection.values():
            record = DecisionProjectionRecord.model_validate(raw)
            if record.resource_type is ResourceType.ALERT:
                if record.provider_release != snapshot.provider_version:
                    return None
                records.append(record)
    except ValueError:
        return None
    records.sort(key=lambda record: (record.source_observed_at, record.resource_id), reverse=True)
    return records


class AlertInboxService:
    def __init__(
        self,
        repository: AlertInboxRepository,
        projections: DecisionEventProjectionRepository,
        integration_mode: TrdBotIntegrationMode | None,
    ) -> None:
        self._repository = repository
        self._projections = projections
        self._integration_mode = integration_mode

    def list_inbox(self, owner_id: UUID, *, limit: int) -> AlertInboxResponse:
        snapshot = self._projections.active_snapshot(owner_id)
        records = None if snapshot is None else _visible_alerts(snapshot)
        provider = provider_status(self._integration_mode, snapshot, invalid=snapshot is not None and records is None)
        if snapshot is None or records is None:
            return AlertInboxResponse(provider=provider, items=())
        records = records[:limit]
        latest = self._repository.latest_for_alerts(owner_id, tuple(record.resource_id for record in records))
        return AlertInboxResponse(
            provider=provider,
            items=tuple(self._item(owner_id, record, latest.get(record.resource_id)) for record in records),
        )

    def transition(
        self,
        owner_id: UUID,
        alert_id: str,
        request: CreateAlertTransitionRequest,
        *,
        idempotency_key: str,
    ) -> AlertStateHistoryResponse:
        existing = self._repository.find_by_idempotency_key(owner_id, idempotency_key)
        state = "acknowledged" if request.action is AlertAction.ACKNOWLEDGE else "snoozed"
        if existing is not None:
            if not self._is_exact_replay(existing, alert_id, state, request):
                raise AlertInboxConflict("idempotency key was used for another alert transition")
            return _history_response(existing)

        record, generation = self._active_alert(owner_id, alert_id)
        if request.evidence_generation != generation or request.source_evidence_checksum != record.source_checksum:
            raise AlertInboxConflict("source alert changed before the owner transition was recorded")
        source = _source(record).model_dump(mode="json")
        try:
            stored, _ = self._repository.record(
                owner_id,
                AlertStateWrite(
                    alert_id=alert_id,
                    state=state,
                    reason_code=ALERT_REASON_CODES[request.action.value],
                    snooze_until=request.snooze_until,
                    evidence_generation=request.evidence_generation,
                    source_evidence_checksum=request.source_evidence_checksum,
                    source_reference=source,
                    occurred_at=request.occurred_at,
                    expected_version=request.expected_version,
                    idempotency_key=idempotency_key,
                ),
            )
        except AlertInboxRepositoryConflict as error:
            raise AlertInboxConflict(str(error)) from error
        return _history_response(stored)

    def _active_alert(self, owner_id: UUID, alert_id: str) -> tuple[DecisionProjectionRecord, int]:
        snapshot = self._projections.active_snapshot(owner_id)
        records = None if snapshot is None else _visible_alerts(snapshot)
        if snapshot is None or records is None:
            raise AlertInboxNotFound("active alert evidence is unavailable")
        record = next((item for item in records if item.resource_id == alert_id), None)
        if record is None:
            raise AlertInboxNotFound("alert evidence is unavailable")
        return record, snapshot.generation

    def _item(
        self,
        owner_id: UUID,
        record: DecisionProjectionRecord,
        latest: AlertStateView | None,
    ) -> AlertInboxItemResponse:
        history = self._repository.list_for_alert(owner_id, record.resource_id)
        state = AlertState.OPEN if latest is None else AlertState(latest.state)
        snooze_until = None if latest is None else latest.snooze_until
        if state is AlertState.SNOOZED and snooze_until is not None and snooze_until <= datetime.now(UTC):
            state = AlertState.OPEN
        source_state = record.payload.get("state", record.payload.get("status"))
        if isinstance(source_state, str) and source_state in {
            AlertState.RESOLVED.value,
            AlertState.EXPIRED.value,
        }:
            state = AlertState(source_state)
            snooze_until = None
        return AlertInboxItemResponse(
            alert_id=record.resource_id,
            local_state=state,
            current_version=0 if latest is None else latest.state_version,
            snooze_until=snooze_until,
            source=_source(record),
            evidence=record.payload,
            evidence_sha256=record.payload_sha256,
            history=tuple(_history_response(item) for item in history),
        )

    @staticmethod
    def _is_exact_replay(
        existing: AlertStateView,
        alert_id: str,
        state: str,
        request: CreateAlertTransitionRequest,
    ) -> bool:
        return (
            existing.alert_id == alert_id
            and existing.state == state
            and existing.reason_code == ALERT_REASON_CODES[request.action.value]
            and existing.snooze_until == request.snooze_until
            and existing.evidence_generation == request.evidence_generation
            and existing.source_evidence_checksum == request.source_evidence_checksum
            and existing.occurred_at == request.occurred_at
            and existing.state_version - 1 == request.expected_version
        )
