from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Final, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from nexora.adapters.postgresql.decision_projection import DecisionEventProjectionRepository
from nexora.adapters.postgresql.outcome_journal import (
    OutcomeJournalEntryView,
    OutcomeJournalRepository,
    OutcomeJournalRepositoryConflict,
    OutcomeJournalRepositoryNotFound,
    OutcomeJournalWrite,
)
from nexora.adapters.trd_bot import ResourceType, SourceReference
from nexora.decision_event_projection import DecisionProjectionRecord

OUTCOME_JOURNAL_SCHEMA_VERSION: Final = "nexora-outcome-journal-v1"


class OutcomeJournalError(RuntimeError):
    pass


class OutcomeJournalNotFound(OutcomeJournalError):
    pass


class OutcomeJournalConflict(OutcomeJournalError):
    pass


class OutcomeJournalValidationError(OutcomeJournalError):
    pass


class OutcomeJournalEntryKind(StrEnum):
    OWNER_NOTE = "owner_note"
    REVIEW_RATIONALE = "review_rationale"
    OBSERVED_OUTCOME = "observed_outcome"
    EXPECTATION_COMPARISON = "expectation_comparison"
    LESSON = "lesson"
    CORRECTION = "correction"


class OutcomeUncertaintyLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class OutcomeSourceKind(StrEnum):
    PROVIDER_EVIDENCE = "provider_evidence"
    PORTFOLIO_SNAPSHOT = "portfolio_snapshot"
    MANUAL_OBSERVATION = "manual_observation"
    EXTERNAL_RECORD = "external_record"


class OutcomeJournalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _trimmed(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be blank")
    return normalized


class OutcomeSourceLineage(OutcomeJournalModel):
    schema_version: Literal["nexora-outcome-source-lineage-v1"] = "nexora-outcome-source-lineage-v1"
    source_kind: OutcomeSourceKind
    source_id: str = Field(min_length=1, max_length=160)
    source_version: str | None = Field(default=None, min_length=1, max_length=80)
    observed_at: datetime
    checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    _source_id_trimmed = field_validator("source_id")(_trimmed)
    _source_version_trimmed = field_validator("source_version")(
        lambda value: None if value is None else _trimmed(value)
    )
    _observed_at_utc = field_validator("observed_at")(_utc)


class CreateOutcomeJournalEntryRequest(OutcomeJournalModel):
    entry_kind: OutcomeJournalEntryKind
    content: str = Field(min_length=1, max_length=4000)
    uncertainty_level: OutcomeUncertaintyLevel
    uncertainty_note: str | None = Field(default=None, min_length=1, max_length=500)
    review_id: UUID | None = None
    portfolio_id: UUID | None = None
    simulated_position_reference: str | None = Field(default=None, min_length=1, max_length=160)
    source_lineage: OutcomeSourceLineage | None = None
    occurred_at: datetime
    supersedes_entry_id: UUID | None = None

    _content_trimmed = field_validator("content")(_trimmed)
    _uncertainty_note_trimmed = field_validator("uncertainty_note")(
        lambda value: None if value is None else _trimmed(value)
    )
    _simulated_position_trimmed = field_validator("simulated_position_reference")(
        lambda value: None if value is None else _trimmed(value)
    )
    _occurred_at_utc = field_validator("occurred_at")(_utc)

    @model_validator(mode="after")
    def validate_entry(self) -> Self:
        if self.occurred_at > datetime.now(UTC):
            raise ValueError("occurred_at must not be in the future")
        if (self.entry_kind is OutcomeJournalEntryKind.CORRECTION) != (self.supersedes_entry_id is not None):
            raise ValueError("correction requires exactly one superseded entry")
        if self.entry_kind is OutcomeJournalEntryKind.OBSERVED_OUTCOME and self.source_lineage is None:
            raise ValueError("observed outcome requires source lineage")
        if self.source_lineage is not None and self.source_lineage.observed_at > self.occurred_at:
            raise ValueError("source observation must not be after the journal occurrence")
        return self


class DecisionJournalSourceResponse(OutcomeJournalModel):
    schema_version: Literal["nexora-source-reference-v1"]
    source_product: Literal["trd_bot"]
    source_version: str
    resource_type: str
    resource_id: str
    resource_schema_version: str
    observed_at: datetime
    checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    _observed_at_utc = field_validator("observed_at")(_utc)


class OutcomeJournalEntryResponse(OutcomeJournalModel):
    schema_version: Literal["nexora-outcome-journal-v1"] = OUTCOME_JOURNAL_SCHEMA_VERSION
    entry_id: UUID
    decision_id: str
    entry_kind: OutcomeJournalEntryKind
    content: str
    uncertainty_level: OutcomeUncertaintyLevel
    uncertainty_note: str | None
    review_id: UUID | None
    portfolio_id: UUID | None
    simulated_position_reference: str | None
    decision_evidence_generation: int = Field(ge=1)
    decision_evidence_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision_source_reference: DecisionJournalSourceResponse
    source_lineage: OutcomeSourceLineage | None
    occurred_at: datetime
    recorded_at: datetime
    supersedes_entry_id: UUID | None
    author_kind: Literal["owner"] = "owner"
    append_only: Literal[True] = True
    ai_generated: Literal[False] = False
    provider_rewritable: Literal[False] = False
    execution_authorization: Literal[False] = False
    transaction_created: Literal[False] = False
    order_intent_created: Literal[False] = False


class OutcomeJournalListResponse(OutcomeJournalModel):
    schema_version: Literal["nexora-outcome-journal-v1"] = OUTCOME_JOURNAL_SCHEMA_VERSION
    decision_id: str
    items: tuple[OutcomeJournalEntryResponse, ...]


def _response(view: OutcomeJournalEntryView) -> OutcomeJournalEntryResponse:
    return OutcomeJournalEntryResponse(
        entry_id=view.entry_id,
        decision_id=view.decision_id,
        entry_kind=OutcomeJournalEntryKind(view.entry_kind),
        content=view.content,
        uncertainty_level=OutcomeUncertaintyLevel(view.uncertainty_level),
        uncertainty_note=view.uncertainty_note,
        review_id=view.review_id,
        portfolio_id=view.portfolio_id,
        simulated_position_reference=view.simulated_position_reference,
        decision_evidence_generation=view.decision_evidence_generation,
        decision_evidence_checksum=view.decision_evidence_checksum,
        decision_source_reference=DecisionJournalSourceResponse.model_validate(view.decision_source_reference),
        source_lineage=(
            None if view.source_lineage is None else OutcomeSourceLineage.model_validate(view.source_lineage)
        ),
        occurred_at=view.occurred_at,
        recorded_at=view.recorded_at,
        supersedes_entry_id=view.supersedes_entry_id,
    )


class OutcomeJournalService:
    def __init__(
        self,
        repository: OutcomeJournalRepository,
        projections: DecisionEventProjectionRepository,
    ) -> None:
        self._repository = repository
        self._projections = projections

    def list_for_decision(
        self,
        owner_id: UUID,
        decision_id: str,
        *,
        limit: int,
    ) -> OutcomeJournalListResponse:
        return OutcomeJournalListResponse(
            decision_id=decision_id,
            items=tuple(
                _response(entry) for entry in self._repository.list_for_decision(owner_id, decision_id, limit=limit)
            ),
        )

    def record(
        self,
        owner_id: UUID,
        decision_id: str,
        request: CreateOutcomeJournalEntryRequest,
        *,
        idempotency_key: str,
    ) -> OutcomeJournalEntryResponse:
        existing = self._repository.find_by_idempotency_key(owner_id, idempotency_key)
        if existing is not None:
            if not self._is_exact_replay(existing, decision_id, request):
                raise OutcomeJournalConflict("idempotency key was used for another journal entry")
            return _response(existing)

        record, generation = self._active_decision(owner_id, decision_id)
        if request.occurred_at < record.source_observed_at:
            raise OutcomeJournalValidationError("journal occurrence must not precede the linked decision evidence")
        source = SourceReference(
            schema_version="nexora-source-reference-v1",
            source_product="trd_bot",
            source_version=record.provider_release,
            resource_type=record.resource_type.value,
            resource_id=record.resource_id,
            resource_schema_version=record.source_schema_version,
            observed_at=record.source_observed_at,
            checksum=record.source_checksum,
        )
        try:
            stored, _ = self._repository.record(
                owner_id,
                OutcomeJournalWrite(
                    decision_id=decision_id,
                    entry_kind=request.entry_kind.value,
                    content=request.content,
                    uncertainty_level=request.uncertainty_level.value,
                    uncertainty_note=request.uncertainty_note,
                    review_id=request.review_id,
                    portfolio_id=request.portfolio_id,
                    simulated_position_reference=request.simulated_position_reference,
                    decision_evidence_generation=generation,
                    decision_evidence_checksum=record.source_checksum,
                    decision_source_reference=source.model_dump(mode="json"),
                    source_lineage=(
                        None if request.source_lineage is None else request.source_lineage.model_dump(mode="json")
                    ),
                    occurred_at=request.occurred_at,
                    supersedes_entry_id=request.supersedes_entry_id,
                    idempotency_key=idempotency_key,
                ),
            )
        except OutcomeJournalRepositoryNotFound as error:
            raise OutcomeJournalNotFound(str(error)) from error
        except OutcomeJournalRepositoryConflict as error:
            raise OutcomeJournalConflict(str(error)) from error
        return _response(stored)

    @staticmethod
    def _is_exact_replay(
        existing: OutcomeJournalEntryView,
        decision_id: str,
        request: CreateOutcomeJournalEntryRequest,
    ) -> bool:
        requested_lineage = None if request.source_lineage is None else request.source_lineage.model_dump(mode="json")
        return (
            existing.decision_id == decision_id
            and existing.entry_kind == request.entry_kind.value
            and existing.content == request.content
            and existing.uncertainty_level == request.uncertainty_level.value
            and existing.uncertainty_note == request.uncertainty_note
            and existing.review_id == request.review_id
            and existing.portfolio_id == request.portfolio_id
            and existing.simulated_position_reference == request.simulated_position_reference
            and existing.source_lineage == requested_lineage
            and existing.occurred_at == request.occurred_at
            and existing.supersedes_entry_id == request.supersedes_entry_id
        )

    def _active_decision(self, owner_id: UUID, decision_id: str) -> tuple[DecisionProjectionRecord, int]:
        snapshot = self._projections.active_snapshot(owner_id)
        if snapshot is None:
            raise OutcomeJournalNotFound("active decision evidence is unavailable")
        try:
            records = tuple(DecisionProjectionRecord.model_validate(raw) for raw in snapshot.projection.values())
        except ValueError as error:
            raise OutcomeJournalValidationError("active decision evidence is invalid") from error
        record = next(
            (
                item
                for item in records
                if item.resource_type is ResourceType.DECISION_EVALUATION and item.resource_id == decision_id
            ),
            None,
        )
        if record is None:
            raise OutcomeJournalNotFound("decision evidence is unavailable")
        if record.provider_release != snapshot.provider_version:
            raise OutcomeJournalValidationError("decision evidence provider lineage is invalid")
        return record, snapshot.generation
