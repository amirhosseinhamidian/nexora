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

from nexora.adapters.postgresql.models import AlertStateHistoryRecord, OwnerAlertStateRecord


class AlertInboxRepositoryConflict(RuntimeError):
    pass


class AlertInboxIdempotencyConflict(AlertInboxRepositoryConflict):
    pass


@dataclass(frozen=True, slots=True)
class AlertStateWrite:
    alert_id: str
    state: str
    reason_code: str
    snooze_until: datetime | None
    evidence_generation: int
    source_evidence_checksum: str
    source_reference: dict[str, Any]
    occurred_at: datetime
    expected_version: int
    idempotency_key: str

    def checksum(self) -> str:
        payload = {
            "alert_id": self.alert_id,
            "evidence_generation": self.evidence_generation,
            "expected_version": self.expected_version,
            "occurred_at": self.occurred_at.isoformat(),
            "reason_code": self.reason_code,
            "snooze_until": None if self.snooze_until is None else self.snooze_until.isoformat(),
            "source_evidence_checksum": self.source_evidence_checksum,
            "source_reference": self.source_reference,
            "state": self.state,
        }
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class AlertStateView:
    alert_history_id: UUID
    alert_id: str
    state_version: int
    state: str
    reason_code: str
    snooze_until: datetime | None
    evidence_generation: int
    source_evidence_checksum: str
    source_reference: dict[str, Any]
    occurred_at: datetime
    recorded_at: datetime


def _view(record: AlertStateHistoryRecord) -> AlertStateView:
    return AlertStateView(
        alert_history_id=record.alert_history_id,
        alert_id=record.alert_id,
        state_version=record.state_version,
        state=record.state,
        reason_code=record.reason_code,
        snooze_until=record.snooze_until,
        evidence_generation=record.evidence_generation,
        source_evidence_checksum=record.source_evidence_checksum,
        source_reference=dict(record.source_reference),
        occurred_at=record.occurred_at,
        recorded_at=record.recorded_at,
    )


class AlertInboxRepository:
    """Append-only owner alert state history with an optimistic head."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def record(self, owner_id: UUID, write: AlertStateWrite) -> tuple[AlertStateView, bool]:
        request_sha256 = write.checksum()
        with self._session_factory() as session, session.begin():
            replay = session.scalar(
                select(AlertStateHistoryRecord).where(
                    AlertStateHistoryRecord.owner_id == owner_id,
                    AlertStateHistoryRecord.idempotency_key == write.idempotency_key,
                )
            )
            if replay is not None:
                if replay.request_sha256 != request_sha256:
                    raise AlertInboxIdempotencyConflict("idempotency key was used for another alert transition")
                return _view(replay), True

            session.execute(
                insert(OwnerAlertStateRecord)
                .values(
                    alert_state_id=uuid4(),
                    owner_id=owner_id,
                    alert_id=write.alert_id,
                    current_version=0,
                )
                .on_conflict_do_nothing(index_elements=["owner_id", "alert_id"])
            )
            state = session.execute(
                select(OwnerAlertStateRecord)
                .where(
                    OwnerAlertStateRecord.owner_id == owner_id,
                    OwnerAlertStateRecord.alert_id == write.alert_id,
                )
                .with_for_update()
            ).scalar_one()
            if state.current_version != write.expected_version:
                raise AlertInboxRepositoryConflict("alert state version changed")

            recorded_at = datetime.now(UTC)
            history = AlertStateHistoryRecord(
                alert_history_id=uuid4(),
                owner_id=owner_id,
                alert_id=write.alert_id,
                state_version=state.current_version + 1,
                state=write.state,
                reason_code=write.reason_code,
                snooze_until=write.snooze_until,
                evidence_generation=write.evidence_generation,
                source_evidence_checksum=write.source_evidence_checksum,
                source_reference=write.source_reference,
                occurred_at=write.occurred_at,
                recorded_at=recorded_at,
                idempotency_key=write.idempotency_key,
                request_sha256=request_sha256,
            )
            session.add(history)
            session.flush()
            state.current_version = history.state_version
            state.latest_history_id = history.alert_history_id
            state.updated_at = recorded_at
            session.flush()
            return _view(history), False

    def find_by_idempotency_key(self, owner_id: UUID, idempotency_key: str) -> AlertStateView | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(AlertStateHistoryRecord).where(
                    AlertStateHistoryRecord.owner_id == owner_id,
                    AlertStateHistoryRecord.idempotency_key == idempotency_key,
                )
            )
        return None if record is None else _view(record)

    def list_for_alert(self, owner_id: UUID, alert_id: str) -> tuple[AlertStateView, ...]:
        with self._session_factory() as session:
            records = session.scalars(
                select(AlertStateHistoryRecord)
                .where(
                    AlertStateHistoryRecord.owner_id == owner_id,
                    AlertStateHistoryRecord.alert_id == alert_id,
                )
                .order_by(AlertStateHistoryRecord.state_version)
            ).all()
        return tuple(_view(record) for record in records)

    def latest_for_alerts(self, owner_id: UUID, alert_ids: tuple[str, ...]) -> dict[str, AlertStateView]:
        if not alert_ids:
            return {}
        with self._session_factory() as session:
            rows = session.execute(
                select(AlertStateHistoryRecord)
                .join(
                    OwnerAlertStateRecord,
                    (OwnerAlertStateRecord.owner_id == AlertStateHistoryRecord.owner_id)
                    & (OwnerAlertStateRecord.latest_history_id == AlertStateHistoryRecord.alert_history_id),
                )
                .where(
                    AlertStateHistoryRecord.owner_id == owner_id,
                    AlertStateHistoryRecord.alert_id.in_(alert_ids),
                )
            ).scalars()
            records = rows.all()
        return {record.alert_id: _view(record) for record in records}
