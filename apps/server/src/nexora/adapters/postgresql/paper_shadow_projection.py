from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from nexora.adapters.postgresql.models import ImmutableSourceEvidence, SourceReference
from nexora.paper_shadow_projection import (
    PaperShadowProjectionView,
    ProjectionSourceEvidence,
    rebuild_paper_shadow_projection,
)

PROJECTABLE_SOURCE_TYPES = (
    "snapshot.paper_shadow_portfolio",
    "snapshot.paper_shadow_position",
    "simulation.position.opened.v1",
    "simulation.position.updated.v1",
    "simulation.position.closed.v1",
)


class PaperShadowProjectionRepository:
    """Rebuild an owner-scoped read model from immutable TRD Bot evidence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def rebuild(self, *, owner_id: UUID) -> PaperShadowProjectionView:
        with self._session_factory() as session:
            rows = session.execute(
                select(SourceReference, ImmutableSourceEvidence)
                .join(
                    ImmutableSourceEvidence,
                    ImmutableSourceEvidence.source_reference_id == SourceReference.source_reference_id,
                )
                .where(
                    SourceReference.owner_id == owner_id,
                    SourceReference.source_system == "trd_bot",
                    SourceReference.source_entity_type.in_(PROJECTABLE_SOURCE_TYPES),
                )
                .order_by(
                    SourceReference.source_observed_at,
                    SourceReference.source_entity_type,
                    SourceReference.source_entity_id,
                    SourceReference.source_version,
                )
            ).all()
        evidence = tuple(
            ProjectionSourceEvidence(
                source_reference_id=reference.source_reference_id,
                source_entity_type=reference.source_entity_type,
                source_entity_id=reference.source_entity_id,
                source_schema_version=reference.source_schema_version,
                source_version=reference.source_version,
                source_observed_at=reference.source_observed_at,
                payload=dict(item.payload),
                payload_sha256=item.payload_sha256,
            )
            for reference, item in rows
        )
        return rebuild_paper_shadow_projection(evidence)
