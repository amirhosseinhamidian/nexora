from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from nexora.adapters.postgresql.models import (
    DecisionReviewRecord,
    OutcomeJournalEntryRecord,
    OwnerProfile,
    PortfolioRecord,
)


class OutcomeJournalRepositoryError(RuntimeError):
    pass


class OutcomeJournalRepositoryNotFound(OutcomeJournalRepositoryError):
    pass


class OutcomeJournalRepositoryConflict(OutcomeJournalRepositoryError):
    pass


class OutcomeJournalIdempotencyConflict(OutcomeJournalRepositoryConflict):
    pass


@dataclass(frozen=True, slots=True)
class OutcomeJournalWrite:
    decision_id: str
    entry_kind: str
    content: str
    uncertainty_level: str
    uncertainty_note: str | None
    review_id: UUID | None
    portfolio_id: UUID | None
    simulated_position_reference: str | None
    decision_evidence_generation: int
    decision_evidence_checksum: str
    decision_source_reference: dict[str, Any]
    source_lineage: dict[str, Any] | None
    occurred_at: datetime
    supersedes_entry_id: UUID | None
    idempotency_key: str

    def checksum(self) -> str:
        payload = {
            "content": self.content,
            "decision_evidence_checksum": self.decision_evidence_checksum,
            "decision_evidence_generation": self.decision_evidence_generation,
            "decision_id": self.decision_id,
            "decision_source_reference": self.decision_source_reference,
            "entry_kind": self.entry_kind,
            "occurred_at": self.occurred_at.isoformat(),
            "portfolio_id": None if self.portfolio_id is None else str(self.portfolio_id),
            "review_id": None if self.review_id is None else str(self.review_id),
            "simulated_position_reference": self.simulated_position_reference,
            "source_lineage": self.source_lineage,
            "supersedes_entry_id": (None if self.supersedes_entry_id is None else str(self.supersedes_entry_id)),
            "uncertainty_level": self.uncertainty_level,
            "uncertainty_note": self.uncertainty_note,
        }
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class OutcomeJournalEntryView:
    entry_id: UUID
    decision_id: str
    entry_kind: str
    content: str
    uncertainty_level: str
    uncertainty_note: str | None
    review_id: UUID | None
    portfolio_id: UUID | None
    simulated_position_reference: str | None
    decision_evidence_generation: int
    decision_evidence_checksum: str
    decision_source_reference: dict[str, Any]
    source_lineage: dict[str, Any] | None
    occurred_at: datetime
    recorded_at: datetime
    supersedes_entry_id: UUID | None
    idempotency_key: str


def _view(record: OutcomeJournalEntryRecord) -> OutcomeJournalEntryView:
    return OutcomeJournalEntryView(
        entry_id=record.entry_id,
        decision_id=record.decision_id,
        entry_kind=record.entry_kind,
        content=record.content,
        uncertainty_level=record.uncertainty_level,
        uncertainty_note=record.uncertainty_note,
        review_id=record.review_id,
        portfolio_id=record.portfolio_id,
        simulated_position_reference=record.simulated_position_reference,
        decision_evidence_generation=record.decision_evidence_generation,
        decision_evidence_checksum=record.decision_evidence_checksum,
        decision_source_reference=dict(record.decision_source_reference),
        source_lineage=None if record.source_lineage is None else dict(record.source_lineage),
        occurred_at=record.occurred_at,
        recorded_at=record.recorded_at,
        supersedes_entry_id=record.supersedes_entry_id,
        idempotency_key=record.idempotency_key,
    )


class OutcomeJournalRepository:
    """Append-only owner journal with immutable correction and reference links."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_for_decision(
        self,
        owner_id: UUID,
        decision_id: str,
        *,
        limit: int,
    ) -> tuple[OutcomeJournalEntryView, ...]:
        with self._session_factory() as session:
            records = session.scalars(
                select(OutcomeJournalEntryRecord)
                .where(
                    OutcomeJournalEntryRecord.owner_id == owner_id,
                    OutcomeJournalEntryRecord.decision_id == decision_id,
                )
                .order_by(
                    OutcomeJournalEntryRecord.occurred_at.desc(),
                    OutcomeJournalEntryRecord.recorded_at.desc(),
                    OutcomeJournalEntryRecord.entry_id.desc(),
                )
                .limit(limit)
            ).all()
        return tuple(_view(record) for record in records)

    def find_by_idempotency_key(
        self,
        owner_id: UUID,
        idempotency_key: str,
    ) -> OutcomeJournalEntryView | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(OutcomeJournalEntryRecord).where(
                    OutcomeJournalEntryRecord.owner_id == owner_id,
                    OutcomeJournalEntryRecord.idempotency_key == idempotency_key,
                )
            )
        return None if record is None else _view(record)

    def record(
        self,
        owner_id: UUID,
        write: OutcomeJournalWrite,
    ) -> tuple[OutcomeJournalEntryView, bool]:
        request_sha256 = write.checksum()
        with self._session_factory() as session, session.begin():
            self._lock_owner(session, owner_id)
            replay = session.scalar(
                select(OutcomeJournalEntryRecord).where(
                    OutcomeJournalEntryRecord.owner_id == owner_id,
                    OutcomeJournalEntryRecord.idempotency_key == write.idempotency_key,
                )
            )
            if replay is not None:
                if replay.request_sha256 != request_sha256:
                    raise OutcomeJournalIdempotencyConflict("idempotency key was used for another journal entry")
                return _view(replay), True

            self._validate_shape(write)
            self._validate_references(session, owner_id, write)
            recorded_at = datetime.now(UTC)
            record = OutcomeJournalEntryRecord(
                entry_id=uuid4(),
                owner_id=owner_id,
                decision_id=write.decision_id,
                entry_kind=write.entry_kind,
                content=write.content,
                uncertainty_level=write.uncertainty_level,
                uncertainty_note=write.uncertainty_note,
                review_id=write.review_id,
                portfolio_id=write.portfolio_id,
                simulated_position_reference=write.simulated_position_reference,
                decision_evidence_generation=write.decision_evidence_generation,
                decision_evidence_checksum=write.decision_evidence_checksum,
                decision_source_reference=write.decision_source_reference,
                source_lineage=write.source_lineage,
                occurred_at=write.occurred_at,
                recorded_at=recorded_at,
                supersedes_entry_id=write.supersedes_entry_id,
                idempotency_key=write.idempotency_key,
                request_sha256=request_sha256,
                author_kind="owner",
                ai_generated=False,
                provider_rewritable=False,
                execution_authorization=False,
                transaction_created=False,
                order_intent_created=False,
            )
            session.add(record)
            session.flush()
            return _view(record), False

    @staticmethod
    def _lock_owner(session: Session, owner_id: UUID) -> None:
        owner = session.scalar(select(OwnerProfile.owner_id).where(OwnerProfile.owner_id == owner_id).with_for_update())
        if owner is None:
            raise OutcomeJournalRepositoryNotFound("owner is unavailable")

    @staticmethod
    def _validate_shape(write: OutcomeJournalWrite) -> None:
        correction = write.entry_kind == "correction"
        if correction != (write.supersedes_entry_id is not None):
            raise OutcomeJournalRepositoryConflict("correction target does not match entry kind")
        if write.entry_kind == "observed_outcome" and write.source_lineage is None:
            raise OutcomeJournalRepositoryConflict("observed outcome requires source lineage")

    @staticmethod
    def _validate_references(session: Session, owner_id: UUID, write: OutcomeJournalWrite) -> None:
        if write.review_id is not None:
            review = session.scalar(
                select(DecisionReviewRecord.review_id).where(
                    DecisionReviewRecord.owner_id == owner_id,
                    DecisionReviewRecord.review_id == write.review_id,
                    DecisionReviewRecord.decision_id == write.decision_id,
                )
            )
            if review is None:
                raise OutcomeJournalRepositoryNotFound("decision review reference is unavailable")
        if write.portfolio_id is not None:
            portfolio = session.scalar(
                select(PortfolioRecord.portfolio_id).where(
                    PortfolioRecord.owner_id == owner_id,
                    PortfolioRecord.portfolio_id == write.portfolio_id,
                )
            )
            if portfolio is None:
                raise OutcomeJournalRepositoryNotFound("portfolio reference is unavailable")
        if write.supersedes_entry_id is not None:
            target = session.scalar(
                select(OutcomeJournalEntryRecord.entry_id).where(
                    OutcomeJournalEntryRecord.owner_id == owner_id,
                    OutcomeJournalEntryRecord.entry_id == write.supersedes_entry_id,
                    OutcomeJournalEntryRecord.decision_id == write.decision_id,
                )
            )
            if target is None:
                raise OutcomeJournalRepositoryNotFound("superseded journal entry is unavailable")
            existing_correction = session.scalar(
                select(OutcomeJournalEntryRecord.entry_id).where(
                    OutcomeJournalEntryRecord.owner_id == owner_id,
                    OutcomeJournalEntryRecord.supersedes_entry_id == write.supersedes_entry_id,
                )
            )
            if existing_correction is not None:
                raise OutcomeJournalRepositoryConflict("journal entry was already superseded")
