from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
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


class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"
    __table_args__ = (
        CheckConstraint("char_length(credential_id) BETWEEN 16 AND 1024", name="credential_id_length"),
        CheckConstraint("octet_length(public_key) BETWEEN 32 AND 4096", name="public_key_length"),
        CheckConstraint("algorithm IN ('ES256', 'EdDSA')", name="algorithm_allowed"),
        CheckConstraint("sign_count >= 0", name="sign_count_nonnegative"),
        CheckConstraint("jsonb_typeof(transports) = 'array'", name="transports_array"),
        CheckConstraint("last_used_at IS NULL OR last_used_at >= created_at", name="last_used_ordered"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="revoked_ordered"),
        UniqueConstraint("credential_id", name="uq_webauthn_credentials_credential_id"),
        {"schema": SCHEMA_NAME},
    )

    credential_record_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.owner_profiles.owner_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    credential_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    public_key: Mapped[bytes] = mapped_column(nullable=False)
    algorithm: Mapped[str] = mapped_column(String(16), nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    transports: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebAuthnChallenge(Base):
    __tablename__ = "webauthn_challenges"
    __table_args__ = (
        CheckConstraint("challenge_digest ~ '^[0-9a-f]{64}$'", name="challenge_digest_format"),
        CheckConstraint("purpose IN ('registration', 'authentication')", name="purpose_allowed"),
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
        CheckConstraint("consumed_at IS NULL OR consumed_at >= created_at", name="consumed_ordered"),
        UniqueConstraint("challenge_digest", name="uq_webauthn_challenges_digest"),
        {"schema": SCHEMA_NAME},
    )

    challenge_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.owner_profiles.owner_id", ondelete="RESTRICT"), index=True
    )
    challenge_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BootstrapToken(Base):
    __tablename__ = "bootstrap_tokens"
    __table_args__ = (
        CheckConstraint("token_digest ~ '^[0-9a-f]{64}$'", name="token_digest_format"),
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
        CheckConstraint("consumed_at IS NULL OR consumed_at >= created_at", name="consumed_ordered"),
        UniqueConstraint("token_digest", name="uq_bootstrap_tokens_token_digest"),
        {"schema": SCHEMA_NAME},
    )

    bootstrap_token_id: Mapped[UUID] = mapped_column(primary_key=True)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecoveryCode(Base):
    __tablename__ = "recovery_codes"
    __table_args__ = (
        CheckConstraint("code_digest ~ '^[0-9a-f]{64}$'", name="code_digest_format"),
        CheckConstraint("used_at IS NULL OR used_at >= created_at", name="used_ordered"),
        UniqueConstraint("owner_id", "code_digest", name="uq_recovery_codes_owner_digest"),
        {"schema": SCHEMA_NAME},
    )

    recovery_code_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.owner_profiles.owner_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BrowserSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("token_digest ~ '^[0-9a-f]{64}$'", name="token_digest_format"),
        CheckConstraint("csrf_digest ~ '^[0-9a-f]{64}$'", name="csrf_digest_format"),
        CheckConstraint("idle_expires_at > created_at", name="idle_expiry_after_creation"),
        CheckConstraint("absolute_expires_at > created_at", name="absolute_expiry_after_creation"),
        CheckConstraint("idle_expires_at <= absolute_expires_at", name="idle_before_absolute_expiry"),
        CheckConstraint("last_seen_at >= created_at", name="last_seen_ordered"),
        CheckConstraint("rotated_at >= created_at", name="rotated_ordered"),
        CheckConstraint("reauthenticated_at >= created_at", name="reauthenticated_ordered"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="revoked_ordered"),
        CheckConstraint("replaced_at IS NULL OR replaced_at >= created_at", name="replaced_ordered"),
        CheckConstraint(
            "rotation_grace_expires_at IS NULL OR rotation_grace_expires_at > replaced_at",
            name="rotation_grace_ordered",
        ),
        UniqueConstraint("token_digest", name="uq_sessions_token_digest"),
        Index("ix_sessions_active", "owner_id", "revoked_at", "idle_expires_at", "absolute_expires_at"),
        {"schema": SCHEMA_NAME},
    )

    session_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.owner_profiles.owner_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reauthenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotation_grace_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ServiceTokenRecord(Base):
    __tablename__ = "service_tokens"
    __table_args__ = (
        CheckConstraint("principal = 'trd_bot_integration'", name="principal_allowed"),
        CheckConstraint("token_digest ~ '^[0-9a-f]{64}$'", name="token_digest_format"),
        CheckConstraint("jsonb_typeof(scopes) = 'array'", name="scopes_array"),
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="revoked_ordered"),
        UniqueConstraint("token_digest", name="uq_service_tokens_token_digest"),
        {"schema": SCHEMA_NAME},
    )

    service_token_id: Mapped[UUID] = mapped_column(primary_key=True)
    principal: Mapped[str] = mapped_column(String(32), nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SecurityAuditEvent(Base):
    __tablename__ = "security_audit_events"
    __table_args__ = (
        CheckConstraint("char_length(event_type) > 0", name="event_type_nonempty"),
        CheckConstraint("actor_type IN ('owner', 'service', 'system', 'unknown')", name="actor_type_allowed"),
        CheckConstraint("outcome IN ('success', 'failure', 'denied')", name="outcome_allowed"),
        CheckConstraint("reason_code ~ '^[A-Z][A-Z0-9_]{2,79}$'", name="reason_code_format"),
        CheckConstraint(
            "source_class IN ('loopback', 'private_overlay', 'internal_service', 'unknown')",
            name="source_class_allowed",
        ),
        CheckConstraint("ip_address_hmac IS NULL OR ip_address_hmac ~ '^[0-9a-f]{64}$'", name="ip_address_hmac_format"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_object"),
        {"schema": SCHEMA_NAME},
    )

    event_id: Mapped[str] = mapped_column(String(68), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(160), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    source_class: Mapped[str] = mapped_column(String(24), nullable=False)
    ip_address_hmac: Mapped[str | None] = mapped_column(String(64))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")


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


class ProjectionCheckpoint(Base):
    __tablename__ = "projection_checkpoints"
    __table_args__ = (
        CheckConstraint("char_length(consumer_name) > 0", name="consumer_name_nonempty"),
        CheckConstraint("char_length(stream_name) > 0", name="stream_name_nonempty"),
        CheckConstraint("cursor IS NULL OR char_length(cursor) > 0", name="cursor_nonempty"),
        CheckConstraint("last_event_id IS NULL OR char_length(last_event_id) > 0", name="last_event_id_nonempty"),
        CheckConstraint("char_length(provider_version) > 0", name="provider_version_nonempty"),
        CheckConstraint("char_length(contract_version) > 0", name="contract_version_nonempty"),
        CheckConstraint("row_version >= 1", name="row_version_positive"),
        CheckConstraint("updated_at >= created_at", name="timestamps_ordered"),
        UniqueConstraint(
            "owner_id",
            "consumer_name",
            "stream_name",
            name="uq_projection_checkpoints_owner_consumer_stream",
        ),
        {"schema": SCHEMA_NAME},
    )

    checkpoint_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.owner_profiles.owner_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    consumer_name: Mapped[str] = mapped_column(String(80), nullable=False)
    stream_name: Mapped[str] = mapped_column(String(80), nullable=False)
    cursor: Mapped[str | None] = mapped_column(String(512))
    last_event_id: Mapped[str | None] = mapped_column(String(80))
    provider_version: Mapped[str] = mapped_column(String(32), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        CheckConstraint("char_length(job_type) > 0", name="job_type_nonempty"),
        CheckConstraint("char_length(idempotency_key) BETWEEN 16 AND 160", name="idempotency_key_length"),
        CheckConstraint("idempotency_key !~ '[[:space:]]'", name="idempotency_key_no_whitespace"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
        CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="payload_sha256_format"),
        CheckConstraint(
            "status IN ('queued', 'leased', 'retry_wait', 'succeeded', 'dead_letter')",
            name="status_allowed",
        ),
        CheckConstraint("attempt_count >= 0 AND attempt_count <= max_attempts", name="attempt_count_bounded"),
        CheckConstraint("max_attempts BETWEEN 1 AND 20", name="max_attempts_bounded"),
        CheckConstraint(
            "(status = 'leased' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(status IN ('queued', 'retry_wait') AND lease_owner IS NULL AND lease_expires_at IS NULL "
            "AND completed_at IS NULL) OR "
            "(status IN ('succeeded', 'dead_letter') AND lease_owner IS NULL AND lease_expires_at IS NULL "
            "AND completed_at IS NOT NULL)",
            name="status_shape",
        ),
        CheckConstraint("updated_at >= created_at", name="timestamps_ordered"),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_background_jobs_owner_idempotency_key"),
        UniqueConstraint("owner_id", "job_id", name="uq_background_jobs_owner_job"),
        Index(
            "ix_background_jobs_claim",
            "status",
            "available_at",
            "lease_expires_at",
            "created_at",
        ),
        {"schema": SCHEMA_NAME},
    )

    job_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.owner_profiles.owner_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="4")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint("char_length(event_type) > 0", name="event_type_nonempty"),
        CheckConstraint("char_length(aggregate_type) > 0", name="aggregate_type_nonempty"),
        CheckConstraint("char_length(aggregate_id) > 0", name="aggregate_id_nonempty"),
        CheckConstraint("char_length(idempotency_key) BETWEEN 16 AND 160", name="idempotency_key_length"),
        CheckConstraint("idempotency_key !~ '[[:space:]]'", name="idempotency_key_no_whitespace"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
        CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="payload_sha256_format"),
        CheckConstraint("status IN ('pending', 'leased', 'published', 'dead_letter')", name="status_allowed"),
        CheckConstraint("attempt_count >= 0 AND attempt_count <= max_attempts", name="attempt_count_bounded"),
        CheckConstraint("max_attempts BETWEEN 1 AND 20", name="max_attempts_bounded"),
        CheckConstraint(
            "(status = 'leased' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND published_at IS NULL) OR "
            "(status = 'pending' AND lease_owner IS NULL AND lease_expires_at IS NULL "
            "AND published_at IS NULL) OR "
            "(status = 'published' AND lease_owner IS NULL AND lease_expires_at IS NULL "
            "AND published_at IS NOT NULL) OR "
            "(status = 'dead_letter' AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name="status_shape",
        ),
        ForeignKeyConstraint(
            ["owner_id", "background_job_id"],
            [f"{SCHEMA_NAME}.background_jobs.owner_id", f"{SCHEMA_NAME}.background_jobs.job_id"],
            name="fk_outbox_events_owner_job",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_outbox_events_owner_idempotency_key"),
        Index(
            "ix_outbox_events_claim",
            "status",
            "available_at",
            "lease_expires_at",
            "created_at",
        ),
        {"schema": SCHEMA_NAME},
    )

    outbox_event_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.owner_profiles.owner_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    background_job_id: Mapped[UUID | None] = mapped_column()
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
