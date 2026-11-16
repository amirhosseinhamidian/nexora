from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Final, Literal, Self, cast
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from nexora.adapters.postgresql.decision_projection import DecisionEventProjectionRepository
from nexora.adapters.postgresql.decision_review import (
    DecisionReviewRepository,
    DecisionReviewRepositoryConflict,
    DecisionReviewView,
    DecisionReviewWrite,
)
from nexora.adapters.trd_bot import (
    CommandType,
    DecisionReviewCommand,
    ResourceType,
    SourceReference,
    TrdBotAdapterError,
    TrdBotClient,
    TrdBotIntegrationMode,
)
from nexora.decision_event_projection import DecisionProjectionRecord

DECISION_REVIEW_SCHEMA_VERSION: Final = "nexora-human-decision-review-v1"
OWNER_REASON_CODES: Final = {
    "accept": frozenset(
        {
            "owner.accept.evidence_sufficient",
            "owner.accept.portfolio_fit",
            "owner.accept.risk_within_policy",
            "owner.accept.observe_in_paper_shadow",
            "owner.accept.other_with_note",
        }
    ),
    "reject": frozenset(
        {
            "owner.reject.stale_context",
            "owner.reject.low_confidence",
            "owner.reject.data_quality",
            "owner.reject.regime_mismatch",
            "owner.reject.exposure",
            "owner.reject.concentration",
            "owner.reject.policy_limit",
            "owner.reject.uncertainty",
            "owner.reject.portfolio_conflict",
            "owner.reject.other_with_note",
        }
    ),
    "defer": frozenset(
        {
            "owner.defer.evidence_pending",
            "owner.defer.market_context_pending",
            "owner.defer.valuation_missing",
            "owner.defer.provider_degraded",
            "owner.defer.review_later",
            "owner.defer.other_with_note",
        }
    ),
}
REVIEW_ACTION_LOCAL_STATE: Final[dict[str, Literal["accepted", "rejected", "deferred"]]] = {
    "accept": "accepted",
    "reject": "rejected",
    "defer": "deferred",
}


class DecisionReviewError(RuntimeError):
    pass


class DecisionReviewNotFound(DecisionReviewError):
    pass


class DecisionReviewConflict(DecisionReviewError):
    pass


class DecisionReviewValidationError(DecisionReviewError):
    pass


class DecisionReviewAction(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"


class DecisionReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


class CreateDecisionReviewRequest(DecisionReviewModel):
    action: DecisionReviewAction
    portfolio_mode: Literal["paper", "shadow"]
    reason_code: str = Field(min_length=1, max_length=100)
    reason_note: str | None = Field(default=None, min_length=1, max_length=500)
    reviewed_at: datetime
    revisit_at: datetime | None = None
    expected_version: int = Field(ge=0)
    evidence_generation: int = Field(ge=1)
    source_evidence_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    supersedes_review_id: UUID | None = None

    _reviewed_at_utc = field_validator("reviewed_at")(_utc)
    _revisit_at_utc = field_validator("revisit_at")(lambda value: None if value is None else _utc(value))

    @field_validator("reason_note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason note must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_review(self) -> Self:
        if self.reason_code not in OWNER_REASON_CODES[self.action.value]:
            raise ValueError("reason code does not belong to the selected owner action")
        if self.reason_code.endswith(".other_with_note") and self.reason_note is None:
            raise ValueError("other_with_note requires a reason note")
        if self.action is not DecisionReviewAction.DEFER and self.revisit_at is not None:
            raise ValueError("only a deferred review may include revisit_at")
        if self.revisit_at is not None and self.revisit_at <= self.reviewed_at:
            raise ValueError("revisit_at must be after reviewed_at")
        if self.reviewed_at > datetime.now(UTC):
            raise ValueError("reviewed_at must not be in the future")
        return self


class DecisionReviewResponse(DecisionReviewModel):
    schema_version: Literal["nexora-human-decision-review-v1"] = DECISION_REVIEW_SCHEMA_VERSION
    review_id: UUID
    decision_id: str
    review_version: int = Field(ge=1)
    action: DecisionReviewAction
    local_state: Literal["accepted", "rejected", "deferred"]
    portfolio_mode: Literal["paper", "shadow"]
    reason_code: str
    reason_note: str | None
    evidence_generation: int = Field(ge=1)
    source_evidence_checksum: str
    reviewed_at: datetime
    recorded_at: datetime
    revisit_at: datetime | None
    supersedes_review_id: UUID | None
    delivery_status: Literal["pending", "accepted", "duplicate"]
    provider_command_id: str | None
    provider_accepted_at: datetime | None
    delivery_attempt_count: int = Field(ge=0)
    execution_authorization: Literal[False] = False
    transaction_created: Literal[False] = False
    order_intent_created: Literal[False] = False


class DecisionReviewContextResponse(DecisionReviewModel):
    schema_version: Literal["nexora-human-decision-review-v1"] = DECISION_REVIEW_SCHEMA_VERSION
    decision_id: str
    current_version: int = Field(ge=0)
    latest_review_id: UUID | None
    local_state: Literal["review_pending", "accepted", "rejected", "deferred"]
    reviewable: bool
    evidence_generation: int | None = Field(default=None, ge=1)
    source_evidence_checksum: str | None = None
    provider_delivery_required: bool
    reviews: tuple[DecisionReviewResponse, ...]


def _response(view: DecisionReviewView) -> DecisionReviewResponse:
    return DecisionReviewResponse(
        review_id=view.review_id,
        decision_id=view.decision_id,
        review_version=view.review_version,
        action=DecisionReviewAction(view.action),
        local_state=REVIEW_ACTION_LOCAL_STATE[view.action],
        portfolio_mode=cast(Literal["paper", "shadow"], view.portfolio_mode),
        reason_code=view.reason_code,
        reason_note=view.reason_note,
        evidence_generation=view.evidence_generation,
        source_evidence_checksum=view.source_evidence_checksum,
        reviewed_at=view.reviewed_at,
        recorded_at=view.recorded_at,
        revisit_at=view.revisit_at,
        supersedes_review_id=view.supersedes_review_id,
        delivery_status=cast(Literal["pending", "accepted", "duplicate"], view.delivery_status),
        provider_command_id=view.provider_command_id,
        provider_accepted_at=view.provider_accepted_at,
        delivery_attempt_count=view.delivery_attempt_count,
    )


class DecisionReviewService:
    def __init__(
        self,
        repository: DecisionReviewRepository,
        projections: DecisionEventProjectionRepository,
        client: TrdBotClient | None,
        integration_mode: TrdBotIntegrationMode | None,
    ) -> None:
        self._repository = repository
        self._projections = projections
        self._client = client
        self._integration_mode = integration_mode

    def context(self, owner_id: UUID, decision_id: str) -> DecisionReviewContextResponse:
        record, generation = self._active_evidence(owner_id, decision_id, required=False)
        reviews = self._repository.list_for_decision(owner_id, decision_id)
        latest = reviews[-1] if reviews else None
        return DecisionReviewContextResponse(
            decision_id=decision_id,
            current_version=0 if latest is None else latest.review_version,
            latest_review_id=None if latest is None else latest.review_id,
            local_state="review_pending" if latest is None else REVIEW_ACTION_LOCAL_STATE[latest.action],
            reviewable=record is not None,
            evidence_generation=generation,
            source_evidence_checksum=None if record is None else record.source_checksum,
            provider_delivery_required=(self._integration_mode is TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER),
            reviews=tuple(_response(review) for review in reviews),
        )

    def record(
        self,
        owner_id: UUID,
        decision_id: str,
        request: CreateDecisionReviewRequest,
        *,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> DecisionReviewResponse:
        existing = self._repository.find_by_idempotency_key(owner_id, idempotency_key)
        if existing is not None:
            if not self._is_exact_replay(existing, decision_id, request):
                raise DecisionReviewConflict("idempotency key was used for another review")
            source = SourceReference.model_validate(existing.source_reference)
            return _response(self._deliver(owner_id, existing, source, idempotency_key, correlation_id))
        record, generation = self._active_evidence(owner_id, decision_id, required=True)
        assert record is not None and generation is not None
        if request.evidence_generation != generation or request.source_evidence_checksum != record.source_checksum:
            raise DecisionReviewConflict("source evidence changed before review was recorded")
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
        write = DecisionReviewWrite(
            decision_id=decision_id,
            action=request.action.value,
            portfolio_mode=request.portfolio_mode,
            reason_code=request.reason_code,
            reason_note=request.reason_note,
            evidence_generation=request.evidence_generation,
            source_evidence_checksum=request.source_evidence_checksum,
            source_reference=source.model_dump(mode="json"),
            reviewed_at=request.reviewed_at,
            revisit_at=request.revisit_at,
            supersedes_review_id=request.supersedes_review_id,
            expected_version=request.expected_version,
            idempotency_key=idempotency_key,
        )
        try:
            stored, _ = self._repository.record(owner_id, write)
        except DecisionReviewRepositoryConflict as error:
            raise DecisionReviewConflict(str(error)) from error
        delivered = self._deliver(owner_id, stored, source, idempotency_key, correlation_id)
        return _response(delivered)

    @staticmethod
    def _is_exact_replay(
        existing: DecisionReviewView,
        decision_id: str,
        request: CreateDecisionReviewRequest,
    ) -> bool:
        return (
            existing.decision_id == decision_id
            and existing.action == request.action.value
            and existing.portfolio_mode == request.portfolio_mode
            and existing.reason_code == request.reason_code
            and existing.reason_note == request.reason_note
            and existing.evidence_generation == request.evidence_generation
            and existing.source_evidence_checksum == request.source_evidence_checksum
            and existing.reviewed_at == request.reviewed_at
            and existing.revisit_at == request.revisit_at
            and existing.supersedes_review_id == request.supersedes_review_id
            and existing.review_version - 1 == request.expected_version
        )

    def _active_evidence(
        self, owner_id: UUID, decision_id: str, *, required: bool
    ) -> tuple[DecisionProjectionRecord | None, int | None]:
        snapshot = self._projections.active_snapshot(owner_id)
        if snapshot is None:
            if required:
                raise DecisionReviewNotFound("active decision evidence is unavailable")
            return None, None
        try:
            records = tuple(DecisionProjectionRecord.model_validate(raw) for raw in snapshot.projection.values())
        except ValueError as error:
            raise DecisionReviewValidationError("active decision evidence is invalid") from error
        record = next(
            (
                item
                for item in records
                if item.resource_type is ResourceType.DECISION_EVALUATION and item.resource_id == decision_id
            ),
            None,
        )
        if record is None:
            if required:
                raise DecisionReviewNotFound("decision evidence is unavailable")
            return None, None
        if record.provider_release != snapshot.provider_version:
            raise DecisionReviewValidationError("decision evidence provider lineage is invalid")
        return record, snapshot.generation

    def _deliver(
        self,
        owner_id: UUID,
        review: DecisionReviewView,
        source: SourceReference,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> DecisionReviewView:
        if (
            review.delivery_status != "pending"
            or self._client is None
            or self._integration_mode is not TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER
        ):
            return review
        reason = review.reason_code
        if review.reason_note is not None:
            reason = f"{reason}: {review.reason_note}"
        if review.revisit_at is not None:
            reason = f"{reason}; revisit_at={review.revisit_at.isoformat()}"
        command_type = {
            "accept": CommandType.ACCEPT,
            "reject": CommandType.REJECT,
            "defer": CommandType.DEFER,
        }[review.action]
        try:
            if self._client.negotiated_provider_version is None:
                self._client.negotiate(correlation_id=correlation_id)
            receipt = self._client.submit_decision_review(
                DecisionReviewCommand(
                    command_type=command_type,
                    decision_id=review.decision_id,
                    portfolio_mode=cast(Literal["paper", "shadow"], review.portfolio_mode),
                    reviewed_at=review.reviewed_at,
                    reason=reason,
                    evidence=source,
                ),
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
        except (TrdBotAdapterError, httpx.HTTPError):
            self._repository.record_delivery_attempt(owner_id, review.review_id, error_code="PROVIDER_UNAVAILABLE")
            return self._repository.get(owner_id, review.review_id)
        return self._repository.record_delivery_receipt(
            owner_id,
            review.review_id,
            status=receipt.status,
            command_id=receipt.command_id,
            correlation_id=receipt.correlation_id,
            accepted_at=receipt.accepted_at,
        )
