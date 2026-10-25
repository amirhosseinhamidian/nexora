from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nexora.adapters.postgresql.base import SCHEMA_NAME, Base


class OwnerProfile(Base):
    __tablename__ = "owner_profiles"
    __table_args__ = (
        CheckConstraint("owner_key = 'primary_owner'", name="owner_key_singleton"),
        CheckConstraint("locale IN ('fa', 'en')", name="locale_allowed"),
        CheckConstraint("theme IN ('light', 'dark', 'system')", name="theme_allowed"),
        CheckConstraint("char_length(timezone) > 0", name="timezone_nonempty"),
        CheckConstraint("updated_at >= created_at", name="timestamps_ordered"),
        UniqueConstraint("owner_key", name="uq_owner_profiles_owner_key"),
        {"schema": SCHEMA_NAME},
    )

    owner_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_key: Mapped[str] = mapped_column(String(32), nullable=False)
    locale: Mapped[str] = mapped_column(String(2), nullable=False, server_default="fa")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")
    theme: Mapped[str] = mapped_column(String(16), nullable=False, server_default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SourceReference(Base):
    __tablename__ = "source_references"
    __table_args__ = (
        CheckConstraint("source_system = 'trd_bot'", name="source_system_allowed"),
        CheckConstraint("char_length(source_entity_type) > 0", name="source_entity_type_nonempty"),
        CheckConstraint("char_length(source_entity_id) > 0", name="source_entity_id_nonempty"),
        CheckConstraint("char_length(source_schema_version) > 0", name="source_schema_version_nonempty"),
        CheckConstraint("char_length(source_version) > 0", name="source_version_nonempty"),
        CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="payload_sha256_format"),
        UniqueConstraint(
            "owner_id",
            "source_system",
            "source_entity_type",
            "source_entity_id",
            "source_version",
            name="uq_source_references_source_identity",
        ),
        UniqueConstraint(
            "owner_id",
            "source_reference_id",
            "payload_sha256",
            name="uq_source_references_owner_reference_checksum",
        ),
        {"schema": SCHEMA_NAME},
    )

    source_reference_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.owner_profiles.owner_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_system: Mapped[str] = mapped_column(String(32), nullable=False)
    source_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ImmutableSourceEvidence(Base):
    __tablename__ = "immutable_source_evidence"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
        CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="payload_sha256_format"),
        ForeignKeyConstraint(
            ["owner_id", "source_reference_id", "payload_sha256"],
            [
                f"{SCHEMA_NAME}.source_references.owner_id",
                f"{SCHEMA_NAME}.source_references.source_reference_id",
                f"{SCHEMA_NAME}.source_references.payload_sha256",
            ],
            name="fk_evidence_owner_reference_checksum",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("source_reference_id", name="uq_immutable_source_evidence_source_reference_id"),
        {"schema": SCHEMA_NAME},
    )

    evidence_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    source_reference_id: Mapped[UUID] = mapped_column(nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
