from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from nexora.adapters.postgresql.models import DecisionProjectionState


@dataclass(frozen=True, slots=True)
class AggregateProjectionState:
    version: int
    event_id: str | None
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class ActiveProjectionGeneration:
    generation: int
    trigger: str
    provider_version: str
    contract_version: str


@dataclass(frozen=True, slots=True)
class ActiveDecisionProjection:
    generation: int
    trigger: str
    provider_version: str
    contract_version: str
    projection: dict[str, Any]


class DecisionEventProjectionRepository:
    """Read only atomically published owner-scoped decision generations."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def active_generation(self, owner_id: UUID) -> ActiveProjectionGeneration | None:
        with self._session_factory() as session:
            row = session.execute(
                select(DecisionProjectionState).where(
                    DecisionProjectionState.owner_id == owner_id,
                    DecisionProjectionState.status == "active",
                )
            ).scalar_one_or_none()
        if row is None:
            return None
        return ActiveProjectionGeneration(
            generation=row.generation,
            trigger=row.trigger,
            provider_version=row.provider_version,
            contract_version=row.contract_version,
        )

    def active_snapshot(self, owner_id: UUID) -> ActiveDecisionProjection | None:
        """Read generation metadata and projection in one database snapshot."""
        with self._session_factory() as session:
            row = session.execute(
                select(DecisionProjectionState).where(
                    DecisionProjectionState.owner_id == owner_id,
                    DecisionProjectionState.status == "active",
                )
            ).scalar_one_or_none()
        if row is None:
            return None
        return ActiveDecisionProjection(
            generation=row.generation,
            trigger=row.trigger,
            provider_version=row.provider_version,
            contract_version=row.contract_version,
            projection=dict(row.projection),
        )

    def aggregate_state(
        self, owner_id: UUID, aggregate_type: str, aggregate_id: str
    ) -> AggregateProjectionState | None:
        key = f"{aggregate_type}:{aggregate_id}"
        with self._session_factory() as session:
            versions = session.execute(
                select(DecisionProjectionState.aggregate_versions).where(
                    DecisionProjectionState.owner_id == owner_id,
                    DecisionProjectionState.status == "active",
                )
            ).scalar_one_or_none()
        if versions is None:
            return None
        value = versions.get(key)
        if not isinstance(value, dict):
            return None
        version = value.get("version")
        checksum = value.get("payload_sha256")
        event_id = value.get("event_id")
        if not isinstance(version, int) or not isinstance(checksum, str):
            raise RuntimeError("stored decision aggregate state is invalid")
        return AggregateProjectionState(
            version=version,
            event_id=event_id if isinstance(event_id, str) else None,
            payload_sha256=checksum,
        )

    def active_projection(self, owner_id: UUID) -> dict[str, dict[str, Any]]:
        with self._session_factory() as session:
            projection = session.execute(
                select(DecisionProjectionState.projection).where(
                    DecisionProjectionState.owner_id == owner_id,
                    DecisionProjectionState.status == "active",
                )
            ).scalar_one_or_none()
        return {} if projection is None else dict(projection)
