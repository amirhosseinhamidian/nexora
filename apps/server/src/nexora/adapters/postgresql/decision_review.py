from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from nexora.adapters.postgresql.models import (
    DecisionReviewDeliveryRecord,
    DecisionReviewRecord,
    DecisionReviewStateRecord,
)


class DecisionReviewRepositoryConflict(RuntimeError):
    pass


class DecisionReviewIdempotencyConflict(DecisionReviewRepositoryConflict):
    pass


@dataclass(frozen=True, slots=True)
class DecisionReviewWrite:
    decision_id: str
    action: str
    portfolio_mode: str
    reason_code: str
    reason_note: str | None
    evidence_generation: int
    source_evidence_checksum: str
    source_reference: dict[str, Any]
    reviewed_at: datetime
    revisit_at: datetime | None
    supersedes_review_id: UUID | None
    expected_version: int
    idempotency_key: str

    def checksum(self) -> str:
        payload = {
            "action": self.action,
            "decision_id": self.decision_id,
            "evidence_generation": self.evidence_generation,
            "expected_version": self.expected_version,
            "portfolio_mode": self.portfolio_mode,
            "reason_code": self.reason_code,
            "reason_note": self.reason_note,
            "revisit_at": None if self.revisit_at is None else self.revisit_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat(),
            "source_evidence_checksum": self.source_evidence_checksum,
            "source_reference": self.source_reference,
            "supersedes_review_id": (None if self.supersedes_review_id is None else str(self.supersedes_review_id)),
        }
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class DecisionReviewView:
    review_id: UUID
    decision_id: str
    review_version: int
    action: str
    portfolio_mode: str
    reason_code: str
    reason_note: str | None
    evidence_generation: int
    source_evidence_checksum: str
    source_reference: dict[str, Any]
    reviewed_at: datetime
    recorded_at: datetime
    revisit_at: datetime | None
    supersedes_review_id: UUID | None
    delivery_status: str
    provider_command_id: str | None
    provider_accepted_at: datetime | None
    delivery_attempt_count: int


def _view(review: DecisionReviewRecord, delivery: DecisionReviewDeliveryRecord) -> DecisionReviewView:
    return DecisionReviewView(
        review_id=review.review_id,
        decision_id=review.decision_id,
        review_version=review.review_version,
        action=review.action,
        portfolio_mode=review.portfolio_mode,
        reason_code=review.reason_code,
        reason_note=review.reason_note,
        evidence_generation=review.evidence_generation,
        source_evidence_checksum=review.source_evidence_checksum,
        source_reference=dict(review.source_reference),
        reviewed_at=review.reviewed_at,
        recorded_at=review.recorded_at,
        revisit_at=review.revisit_at,
        supersedes_review_id=review.supersedes_review_id,
        delivery_status=delivery.status,
        provider_command_id=delivery.provider_command_id,
        provider_accepted_at=delivery.provider_accepted_at,
        delivery_attempt_count=delivery.attempt_count,
    )


class DecisionReviewRepository:
    """Append-only owner reviews plus a locked optimistic-concurrency head."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def record(self, owner_id: UUID, write: DecisionReviewWrite) -> tuple[DecisionReviewView, bool]:
        request_sha256 = write.checksum()
        with self._session_factory() as session, session.begin():
            replay = session.execute(
                select(DecisionReviewRecord, DecisionReviewDeliveryRecord)
                .join(
                    DecisionReviewDeliveryRecord,
                    (DecisionReviewDeliveryRecord.owner_id == DecisionReviewRecord.owner_id)
                    & (DecisionReviewDeliveryRecord.review_id == DecisionReviewRecord.review_id),
                )
                .where(
                    DecisionReviewRecord.owner_id == owner_id,
                    DecisionReviewRecord.idempotency_key == write.idempotency_key,
                )
            ).one_or_none()
            if replay is not None:
                review, delivery = replay
                if review.request_sha256 != request_sha256:
                    raise DecisionReviewIdempotencyConflict("idempotency key was used for another review")
                return _view(review, delivery), True

            session.execute(
                insert(DecisionReviewStateRecord)
                .values(
                    review_state_id=uuid4(),
                    owner_id=owner_id,
                    decision_id=write.decision_id,
                    current_version=0,
                )
                .on_conflict_do_nothing(index_elements=["owner_id", "decision_id"])
            )
            state = session.execute(
                select(DecisionReviewStateRecord)
                .where(
                    DecisionReviewStateRecord.owner_id == owner_id,
                    DecisionReviewStateRecord.decision_id == write.decision_id,
                )
                .with_for_update()
            ).scalar_one()
            if state.current_version != write.expected_version:
                raise DecisionReviewRepositoryConflict("decision review version changed")
            if state.latest_review_id != write.supersedes_review_id:
                raise DecisionReviewRepositoryConflict("superseded review is not the current review")

            recorded_at = datetime.now(UTC)
            review = DecisionReviewRecord(
                review_id=uuid4(),
                owner_id=owner_id,
                decision_id=write.decision_id,
                review_version=state.current_version + 1,
                action=write.action,
                portfolio_mode=write.portfolio_mode,
                reason_code=write.reason_code,
                reason_note=write.reason_note,
                evidence_generation=write.evidence_generation,
                source_evidence_checksum=write.source_evidence_checksum,
                source_reference=write.source_reference,
                reviewed_at=write.reviewed_at,
                recorded_at=recorded_at,
                revisit_at=write.revisit_at,
                supersedes_review_id=write.supersedes_review_id,
                idempotency_key=write.idempotency_key,
                request_sha256=request_sha256,
                execution_authorization=False,
                transaction_created=False,
                order_intent_created=False,
            )
            delivery = DecisionReviewDeliveryRecord(
                delivery_id=uuid4(),
                owner_id=owner_id,
                review_id=review.review_id,
                status="pending",
                attempt_count=0,
                updated_at=recorded_at,
            )
            session.add_all((review, delivery))
            state.current_version = review.review_version
            state.latest_review_id = review.review_id
            state.updated_at = recorded_at
            session.flush()
            return _view(review, delivery), False

    def find_by_idempotency_key(self, owner_id: UUID, idempotency_key: str) -> DecisionReviewView | None:
        with self._session_factory() as session:
            row = session.execute(
                select(DecisionReviewRecord, DecisionReviewDeliveryRecord)
                .join(
                    DecisionReviewDeliveryRecord,
                    (DecisionReviewDeliveryRecord.owner_id == DecisionReviewRecord.owner_id)
                    & (DecisionReviewDeliveryRecord.review_id == DecisionReviewRecord.review_id),
                )
                .where(
                    DecisionReviewRecord.owner_id == owner_id,
                    DecisionReviewRecord.idempotency_key == idempotency_key,
                )
            ).one_or_none()
        if row is None:
            return None
        review, delivery = row
        return _view(review, delivery)

    def list_for_decision(self, owner_id: UUID, decision_id: str) -> tuple[DecisionReviewView, ...]:
        with self._session_factory() as session:
            rows = session.execute(
                select(DecisionReviewRecord, DecisionReviewDeliveryRecord)
                .join(
                    DecisionReviewDeliveryRecord,
                    (DecisionReviewDeliveryRecord.owner_id == DecisionReviewRecord.owner_id)
                    & (DecisionReviewDeliveryRecord.review_id == DecisionReviewRecord.review_id),
                )
                .where(
                    DecisionReviewRecord.owner_id == owner_id,
                    DecisionReviewRecord.decision_id == decision_id,
                )
                .order_by(DecisionReviewRecord.review_version)
            ).all()
        return tuple(_view(review, delivery) for review, delivery in rows)

    def get(self, owner_id: UUID, review_id: UUID) -> DecisionReviewView:
        with self._session_factory() as session:
            review, delivery = session.execute(
                select(DecisionReviewRecord, DecisionReviewDeliveryRecord)
                .join(
                    DecisionReviewDeliveryRecord,
                    (DecisionReviewDeliveryRecord.owner_id == DecisionReviewRecord.owner_id)
                    & (DecisionReviewDeliveryRecord.review_id == DecisionReviewRecord.review_id),
                )
                .where(
                    DecisionReviewRecord.owner_id == owner_id,
                    DecisionReviewRecord.review_id == review_id,
                )
            ).one()
        return _view(review, delivery)

    def latest_actions(self, owner_id: UUID, decision_ids: tuple[str, ...]) -> dict[str, str]:
        if not decision_ids:
            return {}
        with self._session_factory() as session:
            rows = session.execute(
                select(DecisionReviewStateRecord.decision_id, DecisionReviewRecord.action)
                .join(
                    DecisionReviewRecord,
                    (DecisionReviewRecord.owner_id == DecisionReviewStateRecord.owner_id)
                    & (DecisionReviewRecord.review_id == DecisionReviewStateRecord.latest_review_id),
                )
                .where(
                    DecisionReviewStateRecord.owner_id == owner_id,
                    DecisionReviewStateRecord.decision_id.in_(decision_ids),
                )
            ).all()
        return {decision_id: action for decision_id, action in rows}

    def record_delivery_attempt(self, owner_id: UUID, review_id: UUID, *, error_code: str) -> None:
        with self._session_factory() as session, session.begin():
            delivery = session.execute(
                select(DecisionReviewDeliveryRecord)
                .where(
                    DecisionReviewDeliveryRecord.owner_id == owner_id,
                    DecisionReviewDeliveryRecord.review_id == review_id,
                )
                .with_for_update()
            ).scalar_one()
            delivery.attempt_count += 1
            delivery.last_error_code = error_code
            delivery.updated_at = datetime.now(UTC)

    def record_delivery_receipt(
        self,
        owner_id: UUID,
        review_id: UUID,
        *,
        status: str,
        command_id: str,
        correlation_id: UUID,
        accepted_at: datetime,
    ) -> DecisionReviewView:
        with self._session_factory() as session, session.begin():
            row = session.execute(
                select(DecisionReviewRecord, DecisionReviewDeliveryRecord)
                .join(
                    DecisionReviewDeliveryRecord,
                    (DecisionReviewDeliveryRecord.owner_id == DecisionReviewRecord.owner_id)
                    & (DecisionReviewDeliveryRecord.review_id == DecisionReviewRecord.review_id),
                )
                .where(
                    DecisionReviewRecord.owner_id == owner_id,
                    DecisionReviewRecord.review_id == review_id,
                )
                .with_for_update(of=DecisionReviewDeliveryRecord)
            ).one()
            review, delivery = row
            delivery.status = status
            delivery.provider_command_id = command_id
            delivery.provider_correlation_id = correlation_id
            delivery.provider_accepted_at = accepted_at
            delivery.attempt_count += 1
            delivery.last_error_code = None
            delivery.updated_at = datetime.now(UTC)
            session.flush()
            return _view(review, delivery)
