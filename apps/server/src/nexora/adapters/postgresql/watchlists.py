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
    OwnerProfile,
    WatchlistItemRecord,
    WatchlistOperationRecord,
    WatchlistPreferenceRecord,
    WatchlistRecord,
)


class WatchlistRepositoryError(RuntimeError):
    pass


class WatchlistRepositoryNotFound(WatchlistRepositoryError):
    pass


class WatchlistRepositoryConflict(WatchlistRepositoryError):
    pass


class WatchlistIdempotencyConflict(WatchlistRepositoryConflict):
    pass


@dataclass(frozen=True, slots=True)
class WatchlistItemView:
    watchlist_item_id: UUID
    item_kind: str
    reference: str
    label: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class WatchlistPreferencesView:
    presentation_order: str
    minimum_severity: str
    include_resolved: bool
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WatchlistView:
    watchlist_id: UUID
    name: str
    row_version: int
    created_at: datetime
    updated_at: datetime
    preferences: WatchlistPreferencesView
    items: tuple[WatchlistItemView, ...]


@dataclass(frozen=True, slots=True)
class WatchlistCreate:
    name: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class WatchlistItemWrite:
    item_kind: str
    reference: str
    label: str | None
    expected_version: int
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class WatchlistPreferencesWrite:
    presentation_order: str
    minimum_severity: str
    include_resolved: bool
    expected_version: int
    idempotency_key: str


def _checksum(operation_type: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        {"operation_type": operation_type, **payload},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class WatchlistRepository:
    """Owner-scoped watchlist aggregate with idempotent optimistic mutations."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list(self, owner_id: UUID, *, limit: int) -> tuple[WatchlistView, ...]:
        with self._session_factory() as session:
            records = session.scalars(
                select(WatchlistRecord)
                .where(WatchlistRecord.owner_id == owner_id)
                .order_by(WatchlistRecord.created_at, WatchlistRecord.watchlist_id)
                .limit(limit)
            ).all()
            return tuple(self._view(session, record) for record in records)

    def get(self, owner_id: UUID, watchlist_id: UUID) -> WatchlistView:
        with self._session_factory() as session:
            record = self._find_watchlist(session, owner_id, watchlist_id)
            return self._view(session, record)

    def create(self, owner_id: UUID, write: WatchlistCreate) -> tuple[WatchlistView, bool]:
        request_sha256 = _checksum("create", {"name": write.name})
        with self._session_factory() as session, session.begin():
            self._lock_owner(session, owner_id)
            replay = self._find_operation(session, owner_id, write.idempotency_key)
            if replay is not None:
                self._require_replay(replay, "create", request_sha256)
                return self._view(session, self._find_watchlist(session, owner_id, replay.watchlist_id)), True
            duplicate = session.scalar(
                select(WatchlistRecord).where(
                    WatchlistRecord.owner_id == owner_id,
                    WatchlistRecord.name == write.name,
                )
            )
            if duplicate is not None:
                raise WatchlistRepositoryConflict("watchlist name already exists")
            now = datetime.now(UTC)
            record = WatchlistRecord(
                watchlist_id=uuid4(),
                owner_id=owner_id,
                name=write.name,
                row_version=0,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.flush()
            session.add(
                WatchlistPreferenceRecord(
                    preference_id=uuid4(),
                    owner_id=owner_id,
                    watchlist_id=record.watchlist_id,
                    presentation_order="newest_first",
                    minimum_severity="info",
                    include_resolved=False,
                    updated_at=now,
                )
            )
            session.add(
                self._operation(
                    owner_id,
                    record.watchlist_id,
                    "create",
                    0,
                    write.idempotency_key,
                    request_sha256,
                    now,
                )
            )
            session.flush()
            return self._view(session, record), False

    def add_item(
        self,
        owner_id: UUID,
        watchlist_id: UUID,
        write: WatchlistItemWrite,
    ) -> tuple[WatchlistView, bool]:
        request_sha256 = _checksum(
            "add_item",
            {
                "expected_version": write.expected_version,
                "item_kind": write.item_kind,
                "label": write.label,
                "reference": write.reference,
                "watchlist_id": str(watchlist_id),
            },
        )
        with self._session_factory() as session, session.begin():
            self._lock_owner(session, owner_id)
            replay = self._find_operation(session, owner_id, write.idempotency_key)
            if replay is not None:
                self._require_replay(replay, "add_item", request_sha256, watchlist_id)
                return self._view(session, self._find_watchlist(session, owner_id, watchlist_id)), True
            record = self._locked_watchlist(session, owner_id, watchlist_id)
            if record.row_version != write.expected_version:
                raise WatchlistRepositoryConflict("watchlist version changed")
            existing = session.scalar(
                select(WatchlistItemRecord).where(
                    WatchlistItemRecord.owner_id == owner_id,
                    WatchlistItemRecord.watchlist_id == watchlist_id,
                    WatchlistItemRecord.item_kind == write.item_kind,
                    WatchlistItemRecord.reference == write.reference,
                )
            )
            if existing is not None and existing.label != write.label:
                raise WatchlistRepositoryConflict("watchlist item already exists with another label")
            now = datetime.now(UTC)
            if existing is None:
                session.add(
                    WatchlistItemRecord(
                        watchlist_item_id=uuid4(),
                        owner_id=owner_id,
                        watchlist_id=watchlist_id,
                        item_kind=write.item_kind,
                        reference=write.reference,
                        label=write.label,
                        created_at=now,
                    )
                )
                record.row_version += 1
                record.updated_at = now
            session.add(
                self._operation(
                    owner_id,
                    watchlist_id,
                    "add_item",
                    record.row_version,
                    write.idempotency_key,
                    request_sha256,
                    now,
                )
            )
            session.flush()
            return self._view(session, record), existing is not None

    def update_preferences(
        self,
        owner_id: UUID,
        watchlist_id: UUID,
        write: WatchlistPreferencesWrite,
    ) -> tuple[WatchlistView, bool]:
        request_sha256 = _checksum(
            "update_preferences",
            {
                "expected_version": write.expected_version,
                "include_resolved": write.include_resolved,
                "minimum_severity": write.minimum_severity,
                "presentation_order": write.presentation_order,
                "watchlist_id": str(watchlist_id),
            },
        )
        with self._session_factory() as session, session.begin():
            self._lock_owner(session, owner_id)
            replay = self._find_operation(session, owner_id, write.idempotency_key)
            if replay is not None:
                self._require_replay(replay, "update_preferences", request_sha256, watchlist_id)
                return self._view(session, self._find_watchlist(session, owner_id, watchlist_id)), True
            record = self._locked_watchlist(session, owner_id, watchlist_id)
            if record.row_version != write.expected_version:
                raise WatchlistRepositoryConflict("watchlist version changed")
            preferences = session.scalar(
                select(WatchlistPreferenceRecord).where(
                    WatchlistPreferenceRecord.owner_id == owner_id,
                    WatchlistPreferenceRecord.watchlist_id == watchlist_id,
                )
            )
            if preferences is None:
                raise WatchlistRepositoryNotFound("watchlist preferences are unavailable")
            now = datetime.now(UTC)
            preferences.presentation_order = write.presentation_order
            preferences.minimum_severity = write.minimum_severity
            preferences.include_resolved = write.include_resolved
            preferences.updated_at = now
            record.row_version += 1
            record.updated_at = now
            session.add(
                self._operation(
                    owner_id,
                    watchlist_id,
                    "update_preferences",
                    record.row_version,
                    write.idempotency_key,
                    request_sha256,
                    now,
                )
            )
            session.flush()
            return self._view(session, record), False

    @staticmethod
    def _find_operation(session: Session, owner_id: UUID, idempotency_key: str) -> WatchlistOperationRecord | None:
        return session.scalar(
            select(WatchlistOperationRecord).where(
                WatchlistOperationRecord.owner_id == owner_id,
                WatchlistOperationRecord.idempotency_key == idempotency_key,
            )
        )

    @staticmethod
    def _lock_owner(session: Session, owner_id: UUID) -> None:
        owner = session.scalar(select(OwnerProfile.owner_id).where(OwnerProfile.owner_id == owner_id).with_for_update())
        if owner is None:
            raise WatchlistRepositoryNotFound("owner is unavailable")

    @staticmethod
    def _require_replay(
        operation: WatchlistOperationRecord,
        operation_type: str,
        request_sha256: str,
        watchlist_id: UUID | None = None,
    ) -> None:
        if (
            operation.operation_type != operation_type
            or operation.request_sha256 != request_sha256
            or (watchlist_id is not None and operation.watchlist_id != watchlist_id)
        ):
            raise WatchlistIdempotencyConflict("idempotency key was used for another watchlist operation")

    @staticmethod
    def _operation(
        owner_id: UUID,
        watchlist_id: UUID,
        operation_type: str,
        aggregate_version: int,
        idempotency_key: str,
        request_sha256: str,
        recorded_at: datetime,
    ) -> WatchlistOperationRecord:
        return WatchlistOperationRecord(
            operation_id=uuid4(),
            owner_id=owner_id,
            watchlist_id=watchlist_id,
            operation_type=operation_type,
            aggregate_version=aggregate_version,
            idempotency_key=idempotency_key,
            request_sha256=request_sha256,
            recorded_at=recorded_at,
        )

    @staticmethod
    def _find_watchlist(session: Session, owner_id: UUID, watchlist_id: UUID) -> WatchlistRecord:
        record = session.scalar(
            select(WatchlistRecord).where(
                WatchlistRecord.owner_id == owner_id,
                WatchlistRecord.watchlist_id == watchlist_id,
            )
        )
        if record is None:
            raise WatchlistRepositoryNotFound("watchlist is unavailable")
        return record

    @classmethod
    def _locked_watchlist(cls, session: Session, owner_id: UUID, watchlist_id: UUID) -> WatchlistRecord:
        record = session.scalar(
            select(WatchlistRecord)
            .where(
                WatchlistRecord.owner_id == owner_id,
                WatchlistRecord.watchlist_id == watchlist_id,
            )
            .with_for_update()
        )
        if record is None:
            raise WatchlistRepositoryNotFound("watchlist is unavailable")
        return record

    @staticmethod
    def _view(session: Session, record: WatchlistRecord) -> WatchlistView:
        preferences = session.scalar(
            select(WatchlistPreferenceRecord).where(
                WatchlistPreferenceRecord.owner_id == record.owner_id,
                WatchlistPreferenceRecord.watchlist_id == record.watchlist_id,
            )
        )
        if preferences is None:
            raise WatchlistRepositoryNotFound("watchlist preferences are unavailable")
        items = session.scalars(
            select(WatchlistItemRecord)
            .where(
                WatchlistItemRecord.owner_id == record.owner_id,
                WatchlistItemRecord.watchlist_id == record.watchlist_id,
            )
            .order_by(WatchlistItemRecord.created_at, WatchlistItemRecord.watchlist_item_id)
        ).all()
        return WatchlistView(
            watchlist_id=record.watchlist_id,
            name=record.name,
            row_version=record.row_version,
            created_at=record.created_at,
            updated_at=record.updated_at,
            preferences=WatchlistPreferencesView(
                presentation_order=preferences.presentation_order,
                minimum_severity=preferences.minimum_severity,
                include_resolved=preferences.include_resolved,
                updated_at=preferences.updated_at,
            ),
            items=tuple(
                WatchlistItemView(
                    watchlist_item_id=item.watchlist_item_id,
                    item_kind=item.item_kind,
                    reference=item.reference,
                    label=item.label,
                    created_at=item.created_at,
                )
                for item in items
            ),
        )
