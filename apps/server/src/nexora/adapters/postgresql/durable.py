from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session, sessionmaker

from nexora.adapters.postgresql.models import (
    BackgroundJob,
    ImmutableSourceEvidence,
    OutboxEvent,
    ProjectionCheckpoint,
    SourceReference,
    TrdBotSyncReceipt,
)


class DurableWorkError(RuntimeError):
    """Base error for fail-closed durable work coordination."""


class IdempotencyConflict(DurableWorkError):
    """An idempotency key was reused for different immutable input."""


class LeaseLost(DurableWorkError):
    """The caller no longer owns a valid work lease."""


class CheckpointConflict(DurableWorkError):
    """A projection checkpoint changed since it was read."""


def canonical_payload_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def retry_delay(attempt_count: int) -> timedelta:
    """Return the deterministic, bounded retry delay for an attempted delivery."""
    if attempt_count < 1:
        raise ValueError("attempt_count must be positive")
    return timedelta(seconds=min(300, 2 ** (attempt_count - 1)))


@dataclass(frozen=True, slots=True)
class JobClaim:
    job_id: UUID
    owner_id: UUID
    job_type: str
    payload: dict[str, Any]
    attempt_count: int
    max_attempts: int
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class OutboxClaim:
    outbox_event_id: UUID
    owner_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    attempt_count: int
    max_attempts: int
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class CheckpointAdvance:
    consumer_name: str
    stream_name: str
    cursor: str | None
    last_event_id: str | None
    provider_version: str
    contract_version: str
    expected_row_version: int | None


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    idempotency_key: str
    payload: dict[str, Any]
    max_attempts: int = 8


@dataclass(frozen=True, slots=True)
class EnqueuedJob:
    job_type: str
    idempotency_key: str
    payload: dict[str, Any]
    max_attempts: int = 4


@dataclass(frozen=True, slots=True)
class SourceEvidenceWrite:
    source_entity_type: str
    source_entity_id: str
    source_schema_version: str
    source_version: str
    source_observed_at: datetime
    correlation_id: UUID
    payload: dict[str, Any]
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class SyncReceiptWrite:
    event_id: str
    event_type: str
    payload_schema: str
    provider_version: str
    status: str
    reason_code: str | None
    envelope: dict[str, Any]
    envelope_sha256: str


@dataclass(frozen=True, slots=True)
class JobCompletion:
    checkpoint: CheckpointAdvance | None = None
    outbox: tuple[OutboxMessage, ...] = field(default_factory=tuple)
    enqueue: tuple[EnqueuedJob, ...] = field(default_factory=tuple)
    source_evidence: tuple[SourceEvidenceWrite, ...] = field(default_factory=tuple)
    sync_receipts: tuple[SyncReceiptWrite, ...] = field(default_factory=tuple)


class DurableWorkRepository:
    """PostgreSQL-backed jobs, checkpoints, and outbox transaction boundary."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def enqueue_job(
        self,
        *,
        owner_id: UUID,
        job_type: str,
        idempotency_key: str,
        payload: dict[str, Any],
        max_attempts: int = 4,
        available_at: datetime | None = None,
    ) -> UUID:
        payload_hash = canonical_payload_sha256(payload)
        job_id = uuid4()
        when = available_at or datetime.now(UTC)
        with self._session_factory.begin() as session:
            inserted = session.execute(
                postgresql_insert(BackgroundJob)
                .values(
                    job_id=job_id,
                    owner_id=owner_id,
                    job_type=job_type,
                    idempotency_key=idempotency_key,
                    payload=payload,
                    payload_sha256=payload_hash,
                    max_attempts=max_attempts,
                    available_at=when,
                )
                .on_conflict_do_nothing(index_elements=[BackgroundJob.owner_id, BackgroundJob.idempotency_key])
                .returning(BackgroundJob.job_id)
            ).scalar_one_or_none()
            if inserted is not None:
                return inserted
            existing = session.execute(
                select(BackgroundJob).where(
                    BackgroundJob.owner_id == owner_id,
                    BackgroundJob.idempotency_key == idempotency_key,
                )
            ).scalar_one()
            if (
                existing.job_type != job_type
                or existing.payload_sha256 != payload_hash
                or existing.max_attempts != max_attempts
            ):
                raise IdempotencyConflict("job idempotency key was reused with different immutable input")
            return existing.job_id

    def claim_jobs(
        self,
        *,
        worker_id: str,
        job_types: Sequence[str],
        limit: int,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> tuple[JobClaim, ...]:
        if not job_types or limit < 1 or lease_seconds < 1:
            raise ValueError("job_types, limit, and lease_seconds must be positive")
        observed_at = now or datetime.now(UTC)
        with self._session_factory.begin() as session:
            session.execute(
                update(BackgroundJob)
                .where(
                    BackgroundJob.status == "leased",
                    BackgroundJob.job_type.in_(tuple(job_types)),
                    BackgroundJob.lease_expires_at <= observed_at,
                    BackgroundJob.attempt_count >= BackgroundJob.max_attempts,
                )
                .values(
                    status="dead_letter",
                    lease_owner=None,
                    lease_expires_at=None,
                    completed_at=observed_at,
                    updated_at=observed_at,
                    last_error_code="LEASE_EXPIRED_AT_ATTEMPT_LIMIT",
                )
            )
            eligible = or_(
                and_(
                    BackgroundJob.status.in_(("queued", "retry_wait")),
                    BackgroundJob.available_at <= observed_at,
                ),
                and_(
                    BackgroundJob.status == "leased",
                    BackgroundJob.lease_expires_at <= observed_at,
                ),
            )
            jobs = session.execute(
                select(BackgroundJob)
                .where(
                    BackgroundJob.job_type.in_(tuple(job_types)),
                    BackgroundJob.attempt_count < BackgroundJob.max_attempts,
                    eligible,
                )
                .order_by(BackgroundJob.available_at, BackgroundJob.created_at, BackgroundJob.job_id)
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).scalars()
            claims: list[JobClaim] = []
            for job in jobs:
                claimed_at = max(observed_at, job.created_at, job.updated_at)
                expires_at = claimed_at + timedelta(seconds=lease_seconds)
                job.status = "leased"
                job.attempt_count += 1
                job.lease_owner = worker_id
                job.lease_expires_at = expires_at
                job.last_error_code = None
                job.updated_at = claimed_at
                claims.append(
                    JobClaim(
                        job_id=job.job_id,
                        owner_id=job.owner_id,
                        job_type=job.job_type,
                        payload=dict(job.payload),
                        attempt_count=job.attempt_count,
                        max_attempts=job.max_attempts,
                        lease_expires_at=expires_at,
                    )
                )
            return tuple(claims)

    def renew_job_lease(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> datetime:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        observed_at = now or datetime.now(UTC)
        with self._session_factory.begin() as session:
            job = self._active_job(session, job_id, worker_id, observed_at)
            renewed_at = max(observed_at, job.created_at, job.updated_at)
            expires_at = renewed_at + timedelta(seconds=lease_seconds)
            job.lease_expires_at = expires_at
            job.updated_at = renewed_at
        return expires_at

    def complete_job(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        completion: JobCompletion | None = None,
        now: datetime | None = None,
    ) -> None:
        observed_at = now or datetime.now(UTC)
        result = completion or JobCompletion()
        with self._session_factory.begin() as session:
            job = self._active_job(session, job_id, worker_id, observed_at)
            completed_at = max(observed_at, job.created_at, job.updated_at)
            for receipt in result.sync_receipts:
                self._append_sync_receipt(session, job.owner_id, receipt, completed_at)
            for evidence in result.source_evidence:
                self._append_source_evidence(session, job.owner_id, evidence, completed_at)
            if result.checkpoint is not None:
                self._advance_checkpoint(session, job.owner_id, result.checkpoint, completed_at)
            for message in result.outbox:
                self._append_outbox(session, job, message, completed_at)
            for queued in result.enqueue:
                self._enqueue_job(session, job.owner_id, queued, completed_at)
            job.status = "succeeded"
            job.lease_owner = None
            job.lease_expires_at = None
            job.completed_at = completed_at
            job.updated_at = completed_at
            job.last_error_code = None

    def fail_job(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        error_code: str,
        now: datetime | None = None,
    ) -> str:
        observed_at = now or datetime.now(UTC)
        with self._session_factory.begin() as session:
            job = self._active_job(session, job_id, worker_id, observed_at)
            failed_at = max(observed_at, job.created_at, job.updated_at)
            terminal = job.attempt_count >= job.max_attempts
            job.status = "dead_letter" if terminal else "retry_wait"
            job.available_at = failed_at if terminal else failed_at + retry_delay(job.attempt_count)
            job.lease_owner = None
            job.lease_expires_at = None
            job.completed_at = failed_at if terminal else None
            job.updated_at = failed_at
            job.last_error_code = error_code[:80]
            return job.status

    def claim_outbox(
        self,
        *,
        publisher_id: str,
        limit: int,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> tuple[OutboxClaim, ...]:
        if limit < 1 or lease_seconds < 1:
            raise ValueError("limit and lease_seconds must be positive")
        observed_at = now or datetime.now(UTC)
        with self._session_factory.begin() as session:
            session.execute(
                update(OutboxEvent)
                .where(
                    OutboxEvent.status == "leased",
                    OutboxEvent.lease_expires_at <= observed_at,
                    OutboxEvent.attempt_count >= OutboxEvent.max_attempts,
                )
                .values(
                    status="dead_letter",
                    lease_owner=None,
                    lease_expires_at=None,
                    last_error_code="LEASE_EXPIRED_AT_ATTEMPT_LIMIT",
                )
            )
            eligible = or_(
                and_(OutboxEvent.status == "pending", OutboxEvent.available_at <= observed_at),
                and_(OutboxEvent.status == "leased", OutboxEvent.lease_expires_at <= observed_at),
            )
            events = session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.attempt_count < OutboxEvent.max_attempts, eligible)
                .order_by(OutboxEvent.available_at, OutboxEvent.created_at, OutboxEvent.outbox_event_id)
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).scalars()
            claims: list[OutboxClaim] = []
            for event in events:
                claimed_at = max(observed_at, event.created_at)
                expires_at = claimed_at + timedelta(seconds=lease_seconds)
                event.status = "leased"
                event.attempt_count += 1
                event.lease_owner = publisher_id
                event.lease_expires_at = expires_at
                event.last_error_code = None
                claims.append(
                    OutboxClaim(
                        outbox_event_id=event.outbox_event_id,
                        owner_id=event.owner_id,
                        event_type=event.event_type,
                        aggregate_type=event.aggregate_type,
                        aggregate_id=event.aggregate_id,
                        payload=dict(event.payload),
                        attempt_count=event.attempt_count,
                        max_attempts=event.max_attempts,
                        lease_expires_at=expires_at,
                    )
                )
            return tuple(claims)

    def mark_outbox_published(
        self,
        *,
        outbox_event_id: UUID,
        publisher_id: str,
        now: datetime | None = None,
    ) -> None:
        observed_at = now or datetime.now(UTC)
        with self._session_factory.begin() as session:
            event = self._active_outbox(session, outbox_event_id, publisher_id, observed_at)
            published_at = max(observed_at, event.created_at)
            event.status = "published"
            event.lease_owner = None
            event.lease_expires_at = None
            event.published_at = published_at
            event.last_error_code = None

    def fail_outbox(
        self,
        *,
        outbox_event_id: UUID,
        publisher_id: str,
        error_code: str,
        now: datetime | None = None,
    ) -> str:
        observed_at = now or datetime.now(UTC)
        with self._session_factory.begin() as session:
            event = self._active_outbox(session, outbox_event_id, publisher_id, observed_at)
            failed_at = max(observed_at, event.created_at)
            terminal = event.attempt_count >= event.max_attempts
            event.status = "dead_letter" if terminal else "pending"
            event.available_at = failed_at if terminal else failed_at + retry_delay(event.attempt_count)
            event.lease_owner = None
            event.lease_expires_at = None
            event.last_error_code = error_code[:80]
            return event.status

    @staticmethod
    def _active_job(session: Session, job_id: UUID, worker_id: str, now: datetime) -> BackgroundJob:
        job = session.execute(
            select(BackgroundJob).where(BackgroundJob.job_id == job_id).with_for_update()
        ).scalar_one_or_none()
        if (
            job is None
            or job.status != "leased"
            or job.lease_owner != worker_id
            or job.lease_expires_at is None
            or job.lease_expires_at <= now
        ):
            raise LeaseLost("job lease is missing, expired, or owned by another worker")
        return job

    @staticmethod
    def _active_outbox(session: Session, event_id: UUID, publisher_id: str, now: datetime) -> OutboxEvent:
        event = session.execute(
            select(OutboxEvent).where(OutboxEvent.outbox_event_id == event_id).with_for_update()
        ).scalar_one_or_none()
        if (
            event is None
            or event.status != "leased"
            or event.lease_owner != publisher_id
            or event.lease_expires_at is None
            or event.lease_expires_at <= now
        ):
            raise LeaseLost("outbox lease is missing, expired, or owned by another publisher")
        return event

    @staticmethod
    def _advance_checkpoint(
        session: Session,
        owner_id: UUID,
        advance: CheckpointAdvance,
        now: datetime,
    ) -> None:
        checkpoint = session.execute(
            select(ProjectionCheckpoint)
            .where(
                ProjectionCheckpoint.owner_id == owner_id,
                ProjectionCheckpoint.consumer_name == advance.consumer_name,
                ProjectionCheckpoint.stream_name == advance.stream_name,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if checkpoint is None:
            if advance.expected_row_version is not None:
                raise CheckpointConflict("checkpoint does not exist at the expected row version")
            session.add(
                ProjectionCheckpoint(
                    checkpoint_id=uuid4(),
                    owner_id=owner_id,
                    consumer_name=advance.consumer_name,
                    stream_name=advance.stream_name,
                    cursor=advance.cursor,
                    last_event_id=advance.last_event_id,
                    provider_version=advance.provider_version,
                    contract_version=advance.contract_version,
                    row_version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            return
        if advance.expected_row_version != checkpoint.row_version:
            raise CheckpointConflict("checkpoint row version changed")
        checkpoint.cursor = advance.cursor
        checkpoint.last_event_id = advance.last_event_id
        checkpoint.provider_version = advance.provider_version
        checkpoint.contract_version = advance.contract_version
        checkpoint.row_version += 1
        checkpoint.updated_at = now

    @staticmethod
    def _append_outbox(session: Session, job: BackgroundJob, message: OutboxMessage, now: datetime) -> None:
        payload_hash = canonical_payload_sha256(message.payload)
        inserted = session.execute(
            postgresql_insert(OutboxEvent)
            .values(
                outbox_event_id=uuid4(),
                owner_id=job.owner_id,
                background_job_id=job.job_id,
                event_type=message.event_type,
                aggregate_type=message.aggregate_type,
                aggregate_id=message.aggregate_id,
                idempotency_key=message.idempotency_key,
                payload=message.payload,
                payload_sha256=payload_hash,
                max_attempts=message.max_attempts,
                available_at=now,
            )
            .on_conflict_do_nothing(index_elements=[OutboxEvent.owner_id, OutboxEvent.idempotency_key])
            .returning(OutboxEvent.outbox_event_id)
        ).scalar_one_or_none()
        if inserted is not None:
            return
        existing = session.execute(
            select(OutboxEvent).where(
                OutboxEvent.owner_id == job.owner_id,
                OutboxEvent.idempotency_key == message.idempotency_key,
            )
        ).scalar_one()
        identity = (
            existing.background_job_id,
            existing.event_type,
            existing.aggregate_type,
            existing.aggregate_id,
            existing.payload_sha256,
            existing.max_attempts,
        )
        expected = (
            job.job_id,
            message.event_type,
            message.aggregate_type,
            message.aggregate_id,
            payload_hash,
            message.max_attempts,
        )
        if identity != expected:
            raise IdempotencyConflict("outbox idempotency key was reused with different immutable input")

    @staticmethod
    def _enqueue_job(session: Session, owner_id: UUID, queued: EnqueuedJob, now: datetime) -> None:
        payload_hash = canonical_payload_sha256(queued.payload)
        inserted = session.execute(
            postgresql_insert(BackgroundJob)
            .values(
                job_id=uuid4(),
                owner_id=owner_id,
                job_type=queued.job_type,
                idempotency_key=queued.idempotency_key,
                payload=queued.payload,
                payload_sha256=payload_hash,
                max_attempts=queued.max_attempts,
                available_at=now,
            )
            .on_conflict_do_nothing(index_elements=[BackgroundJob.owner_id, BackgroundJob.idempotency_key])
            .returning(BackgroundJob.job_id)
        ).scalar_one_or_none()
        if inserted is not None:
            return
        existing = session.execute(
            select(BackgroundJob).where(
                BackgroundJob.owner_id == owner_id,
                BackgroundJob.idempotency_key == queued.idempotency_key,
            )
        ).scalar_one()
        if (
            existing.job_type != queued.job_type
            or existing.payload_sha256 != payload_hash
            or existing.max_attempts != queued.max_attempts
        ):
            raise IdempotencyConflict("follow-up job idempotency key was reused with different immutable input")

    @staticmethod
    def _append_sync_receipt(
        session: Session,
        owner_id: UUID,
        receipt: SyncReceiptWrite,
        now: datetime,
    ) -> None:
        inserted = session.execute(
            postgresql_insert(TrdBotSyncReceipt)
            .values(
                receipt_id=uuid4(),
                owner_id=owner_id,
                event_id=receipt.event_id,
                event_type=receipt.event_type,
                payload_schema=receipt.payload_schema,
                provider_version=receipt.provider_version,
                status=receipt.status,
                reason_code=receipt.reason_code,
                envelope=receipt.envelope,
                envelope_sha256=receipt.envelope_sha256,
                received_at=now,
            )
            .on_conflict_do_nothing(index_elements=[TrdBotSyncReceipt.owner_id, TrdBotSyncReceipt.event_id])
            .returning(TrdBotSyncReceipt.receipt_id)
        ).scalar_one_or_none()
        if inserted is not None:
            return
        existing = session.execute(
            select(TrdBotSyncReceipt).where(
                TrdBotSyncReceipt.owner_id == owner_id,
                TrdBotSyncReceipt.event_id == receipt.event_id,
            )
        ).scalar_one()
        if existing.envelope_sha256 != receipt.envelope_sha256 or existing.status != receipt.status:
            raise IdempotencyConflict("TRD Bot event ID was replayed with different immutable content")

    @staticmethod
    def _append_source_evidence(
        session: Session,
        owner_id: UUID,
        evidence: SourceEvidenceWrite,
        now: datetime,
    ) -> None:
        reference_id = uuid4()
        inserted = session.execute(
            postgresql_insert(SourceReference)
            .values(
                source_reference_id=reference_id,
                owner_id=owner_id,
                source_system="trd_bot",
                source_entity_type=evidence.source_entity_type,
                source_entity_id=evidence.source_entity_id,
                source_schema_version=evidence.source_schema_version,
                source_version=evidence.source_version,
                source_observed_at=evidence.source_observed_at,
                correlation_id=evidence.correlation_id,
                payload_sha256=evidence.payload_sha256,
                recorded_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    SourceReference.owner_id,
                    SourceReference.source_system,
                    SourceReference.source_entity_type,
                    SourceReference.source_entity_id,
                    SourceReference.source_version,
                ]
            )
            .returning(SourceReference.source_reference_id)
        ).scalar_one_or_none()
        if inserted is None:
            existing = session.execute(
                select(SourceReference).where(
                    SourceReference.owner_id == owner_id,
                    SourceReference.source_system == "trd_bot",
                    SourceReference.source_entity_type == evidence.source_entity_type,
                    SourceReference.source_entity_id == evidence.source_entity_id,
                    SourceReference.source_version == evidence.source_version,
                )
            ).scalar_one()
            if (
                existing.source_schema_version != evidence.source_schema_version
                or existing.payload_sha256 != evidence.payload_sha256
                or existing.correlation_id != evidence.correlation_id
            ):
                raise IdempotencyConflict("source identity was replayed with different immutable content")
            reference_id = existing.source_reference_id
        session.execute(
            postgresql_insert(ImmutableSourceEvidence)
            .values(
                evidence_id=uuid4(),
                owner_id=owner_id,
                source_reference_id=reference_id,
                payload=evidence.payload,
                payload_sha256=evidence.payload_sha256,
                recorded_at=now,
            )
            .on_conflict_do_nothing(index_elements=[ImmutableSourceEvidence.source_reference_id])
        )
