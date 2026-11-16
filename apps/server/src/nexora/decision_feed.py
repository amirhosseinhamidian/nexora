from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nexora.adapters.postgresql.decision_projection import (
    ActiveDecisionProjection,
    DecisionEventProjectionRepository,
)
from nexora.adapters.postgresql.decision_review import DecisionReviewRepository
from nexora.adapters.trd_bot import ResourceType, TrdBotIntegrationMode
from nexora.decision_event_projection import (
    DecisionKind,
    DecisionProjectionRecord,
    LocalDecisionState,
    canonical_json_sha256,
)

DECISION_FEED_SCHEMA_VERSION: Final = "nexora-decision-feed-v1"
VISIBLE_RESOURCE_TYPES: Final = frozenset({ResourceType.DECISION_EVALUATION, ResourceType.CANDIDATE})
REVIEW_ACTION_LOCAL_STATE: Final = {
    "accept": LocalDecisionState.ACCEPTED,
    "reject": LocalDecisionState.REJECTED,
    "defer": LocalDecisionState.DEFERRED,
}


class DecisionFeedError(RuntimeError):
    pass


class DecisionFeedValidationError(DecisionFeedError):
    pass


class DecisionFeedConflict(DecisionFeedError):
    pass


class DecisionEvidenceNotFound(DecisionFeedError):
    pass


class ProviderState(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    DISABLED_INCOMPATIBLE = "disabled_incompatible"


class FeedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProviderStatusResponse(FeedModel):
    state: ProviderState
    reason_code: Literal[
        "ACTIVE_PROJECTION_READY",
        "ACTIVE_PROJECTION_UNAVAILABLE",
        "PROJECTION_EVIDENCE_INVALID",
        "PROVIDER_DISABLED_INCOMPATIBLE",
        "PROVIDER_RUNTIME_UNCONFIGURED",
    ]
    provider_version: str | None = None
    contract_version: str | None = None
    generation: int | None = Field(default=None, ge=1)


class SourceReferenceResponse(FeedModel):
    schema_version: Literal["nexora-source-reference-v1"] = "nexora-source-reference-v1"
    source_product: Literal["trd_bot"] = "trd_bot"
    source_version: str
    resource_type: Literal["decision_evaluation", "candidate"]
    resource_id: str
    resource_schema_version: str
    observed_at: datetime
    checksum: str
    event_id: str | None = None
    aggregate_type: str | None = None
    aggregate_id: str | None = None
    aggregate_version: int | None = None


class DecisionFeedItemResponse(FeedModel):
    resource_type: Literal["decision_evaluation", "candidate"]
    resource_id: str
    decision_kind: DecisionKind
    local_state: LocalDecisionState
    source: SourceReferenceResponse
    evidence: dict[str, Any]
    evidence_sha256: str


class DecisionFeedResponse(FeedModel):
    schema_version: Literal["nexora-decision-feed-v1"] = DECISION_FEED_SCHEMA_VERSION
    provider: ProviderStatusResponse
    items: list[DecisionFeedItemResponse]
    next_cursor: str | None = None


class CandidateDetailResponse(FeedModel):
    schema_version: Literal["nexora-decision-feed-v1"] = DECISION_FEED_SCHEMA_VERSION
    provider: ProviderStatusResponse
    candidate: DecisionFeedItemResponse | None


def _encode_cursor(generation: int, evidence_sha256: str, offset: int) -> str:
    payload = json.dumps(
        {"evidence_sha256": evidence_sha256, "generation": generation, "offset": offset},
        separators=(",", ":"),
        sort_keys=True,
    )
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str, generation: int, evidence_sha256: str) -> int:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.b64decode(cursor + padding, altchars=b"-_", validate=True))
    except (ValueError, binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DecisionFeedValidationError("decision feed cursor is invalid") from error
    if not isinstance(payload, dict) or set(payload) != {"evidence_sha256", "generation", "offset"}:
        raise DecisionFeedValidationError("decision feed cursor is invalid")
    if payload["generation"] != generation or payload["evidence_sha256"] != evidence_sha256:
        raise DecisionFeedConflict("decision feed snapshot changed")
    offset = payload["offset"]
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise DecisionFeedValidationError("decision feed cursor is invalid")
    return offset


def provider_status(
    mode: TrdBotIntegrationMode | None,
    snapshot: ActiveDecisionProjection | None,
    *,
    invalid: bool = False,
) -> ProviderStatusResponse:
    provider_version = None if snapshot is None else snapshot.provider_version
    contract_version = None if snapshot is None else snapshot.contract_version
    generation = None if snapshot is None else snapshot.generation
    if mode is TrdBotIntegrationMode.DISABLED_INCOMPATIBLE_PROVIDER:
        return ProviderStatusResponse(
            state=ProviderState.DISABLED_INCOMPATIBLE,
            reason_code="PROVIDER_DISABLED_INCOMPATIBLE",
            provider_version=provider_version,
            contract_version=contract_version,
            generation=generation,
        )
    if mode is None:
        return ProviderStatusResponse(
            state=ProviderState.DEGRADED,
            reason_code="PROVIDER_RUNTIME_UNCONFIGURED",
            provider_version=provider_version,
            contract_version=contract_version,
            generation=generation,
        )
    if invalid:
        return ProviderStatusResponse(
            state=ProviderState.DEGRADED,
            reason_code="PROJECTION_EVIDENCE_INVALID",
            provider_version=provider_version,
            contract_version=contract_version,
            generation=generation,
        )
    if snapshot is None:
        return ProviderStatusResponse(
            state=ProviderState.DEGRADED,
            reason_code="ACTIVE_PROJECTION_UNAVAILABLE",
        )
    return ProviderStatusResponse(
        state=ProviderState.READY,
        reason_code="ACTIVE_PROJECTION_READY",
        provider_version=provider_version,
        contract_version=contract_version,
        generation=generation,
    )


def _response_item(
    record: DecisionProjectionRecord,
    local_state: LocalDecisionState | None = None,
) -> DecisionFeedItemResponse:
    if record.resource_type not in VISIBLE_RESOURCE_TYPES:
        raise DecisionFeedValidationError("resource is not visible in the decision feed")
    resource_type = cast(Literal["decision_evaluation", "candidate"], record.resource_type.value)
    return DecisionFeedItemResponse(
        resource_type=resource_type,
        resource_id=record.resource_id,
        decision_kind=record.decision_kind,
        local_state=record.local_state if local_state is None else local_state,
        source=SourceReferenceResponse(
            source_version=record.provider_release,
            resource_type=resource_type,
            resource_id=record.resource_id,
            resource_schema_version=record.source_schema_version,
            observed_at=record.source_observed_at,
            checksum=record.source_checksum,
            event_id=record.source_event_id,
            aggregate_type=record.aggregate_type,
            aggregate_id=record.aggregate_id,
            aggregate_version=record.aggregate_version,
        ),
        evidence=record.payload,
        evidence_sha256=record.payload_sha256,
    )


def _visible_records(snapshot: ActiveDecisionProjection) -> list[DecisionProjectionRecord] | None:
    records: list[DecisionProjectionRecord] = []
    try:
        for raw in snapshot.projection.values():
            record = DecisionProjectionRecord.model_validate(raw)
            if record.resource_type in VISIBLE_RESOURCE_TYPES:
                if record.provider_release != snapshot.provider_version:
                    return None
                records.append(record)
    except ValidationError:
        return None
    records.sort(
        key=lambda record: (record.source_observed_at, record.resource_type.value, record.resource_id), reverse=True
    )
    return records


class DecisionFeedService:
    def __init__(
        self,
        repository: DecisionEventProjectionRepository,
        integration_mode: TrdBotIntegrationMode | None,
        review_repository: DecisionReviewRepository | None = None,
    ) -> None:
        self._repository = repository
        self._integration_mode = integration_mode
        self._review_repository = review_repository

    def _local_states(self, owner_id: UUID, records: list[DecisionProjectionRecord]) -> dict[str, LocalDecisionState]:
        if self._review_repository is None:
            return {}
        decision_ids = tuple(
            record.resource_id for record in records if record.resource_type is ResourceType.DECISION_EVALUATION
        )
        actions = self._review_repository.latest_actions(owner_id, decision_ids)
        return {decision_id: REVIEW_ACTION_LOCAL_STATE[action] for decision_id, action in actions.items()}

    def list_feed(self, owner_id: UUID, *, limit: int, cursor: str | None) -> DecisionFeedResponse:
        snapshot = self._repository.active_snapshot(owner_id)
        records = None if snapshot is None else _visible_records(snapshot)
        provider = provider_status(self._integration_mode, snapshot, invalid=snapshot is not None and records is None)
        if snapshot is None or records is None:
            return DecisionFeedResponse(provider=provider, items=[])
        evidence_sha256 = canonical_json_sha256([record.model_dump(mode="json") for record in records])
        offset = 0 if cursor is None else _decode_cursor(cursor, snapshot.generation, evidence_sha256)
        page = records[offset : offset + limit]
        local_states = self._local_states(owner_id, records)
        next_offset = offset + len(page)
        return DecisionFeedResponse(
            provider=provider,
            items=[
                _response_item(
                    record,
                    local_states.get(
                        record.resource_id
                        if record.resource_type is ResourceType.DECISION_EVALUATION
                        else str(record.payload.get("evaluation_id", ""))
                    ),
                )
                for record in page
            ],
            next_cursor=(
                _encode_cursor(snapshot.generation, evidence_sha256, next_offset)
                if next_offset < len(records)
                else None
            ),
        )

    def candidate_detail(self, owner_id: UUID, candidate_id: str) -> CandidateDetailResponse:
        snapshot = self._repository.active_snapshot(owner_id)
        records = None if snapshot is None else _visible_records(snapshot)
        provider = provider_status(self._integration_mode, snapshot, invalid=snapshot is not None and records is None)
        if snapshot is None or records is None:
            return CandidateDetailResponse(provider=provider, candidate=None)
        candidate = next(
            (
                record
                for record in records
                if record.resource_type is ResourceType.CANDIDATE and record.resource_id == candidate_id
            ),
            None,
        )
        if candidate is None:
            raise DecisionEvidenceNotFound("candidate evidence is unavailable")
        states = self._local_states(owner_id, records)
        evaluation_id = candidate.payload.get("evaluation_id")
        local_state = states.get(evaluation_id) if isinstance(evaluation_id, str) else None
        return CandidateDetailResponse(provider=provider, candidate=_response_item(candidate, local_state))
