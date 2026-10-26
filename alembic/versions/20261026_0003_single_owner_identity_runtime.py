"""Add single-owner credentials, sessions, recovery, and security audit state.

Revision ID: 20261026_0003
Revises: 20261025_0002
Create Date: 2026-10-26 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261026_0003"
down_revision: str | None = "20261025_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _owner_fk(table_name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["owner_id"],
        ["nexora.owner_profiles.owner_id"],
        name=op.f(f"fk_{table_name}_owner_id_owner_profiles"),
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "webauthn_credentials",
        sa.Column("credential_record_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("credential_id", sa.String(1024), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("algorithm", sa.String(16), nullable=False),
        sa.Column("sign_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("transports", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(credential_id) BETWEEN 16 AND 1024", name=op.f("ck_webauthn_credentials_credential_id_length")
        ),
        sa.CheckConstraint(
            "octet_length(public_key) BETWEEN 32 AND 4096", name=op.f("ck_webauthn_credentials_public_key_length")
        ),
        sa.CheckConstraint("algorithm IN ('ES256', 'EdDSA')", name=op.f("ck_webauthn_credentials_algorithm_allowed")),
        sa.CheckConstraint("sign_count >= 0", name=op.f("ck_webauthn_credentials_sign_count_nonnegative")),
        sa.CheckConstraint("jsonb_typeof(transports) = 'array'", name=op.f("ck_webauthn_credentials_transports_array")),
        sa.CheckConstraint(
            "last_used_at IS NULL OR last_used_at >= created_at",
            name=op.f("ck_webauthn_credentials_last_used_ordered"),
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at", name=op.f("ck_webauthn_credentials_revoked_ordered")
        ),
        _owner_fk("webauthn_credentials"),
        sa.PrimaryKeyConstraint("credential_record_id", name="pk_webauthn_credentials"),
        sa.UniqueConstraint("credential_id", name="uq_webauthn_credentials_credential_id"),
        schema="nexora",
    )
    op.create_index("ix_webauthn_credentials_owner_id", "webauthn_credentials", ["owner_id"], schema="nexora")

    op.create_table(
        "webauthn_challenges",
        sa.Column("challenge_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("challenge_digest", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "challenge_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_webauthn_challenges_challenge_digest_format")
        ),
        sa.CheckConstraint(
            "purpose IN ('registration', 'authentication')", name=op.f("ck_webauthn_challenges_purpose_allowed")
        ),
        sa.CheckConstraint("expires_at > created_at", name=op.f("ck_webauthn_challenges_expires_after_creation")),
        sa.CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= created_at", name=op.f("ck_webauthn_challenges_consumed_ordered")
        ),
        _owner_fk("webauthn_challenges"),
        sa.PrimaryKeyConstraint("challenge_id", name="pk_webauthn_challenges"),
        sa.UniqueConstraint("challenge_digest", name="uq_webauthn_challenges_digest"),
        schema="nexora",
    )
    op.create_index("ix_webauthn_challenges_owner_id", "webauthn_challenges", ["owner_id"], schema="nexora")

    op.create_table(
        "bootstrap_tokens",
        sa.Column("bootstrap_token_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("token_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_bootstrap_tokens_token_digest_format")),
        sa.CheckConstraint("expires_at > created_at", name=op.f("ck_bootstrap_tokens_expires_after_creation")),
        sa.CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= created_at", name=op.f("ck_bootstrap_tokens_consumed_ordered")
        ),
        sa.PrimaryKeyConstraint("bootstrap_token_id", name="pk_bootstrap_tokens"),
        sa.UniqueConstraint("token_digest", name="uq_bootstrap_tokens_token_digest"),
        schema="nexora",
    )

    op.create_table(
        "recovery_codes",
        sa.Column("recovery_code_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("code_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("code_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_recovery_codes_code_digest_format")),
        sa.CheckConstraint("used_at IS NULL OR used_at >= created_at", name=op.f("ck_recovery_codes_used_ordered")),
        _owner_fk("recovery_codes"),
        sa.PrimaryKeyConstraint("recovery_code_id", name="pk_recovery_codes"),
        sa.UniqueConstraint("owner_id", "code_digest", name="uq_recovery_codes_owner_digest"),
        schema="nexora",
    )
    op.create_index("ix_recovery_codes_owner_id", "recovery_codes", ["owner_id"], schema="nexora")

    op.create_table(
        "sessions",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("csrf_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotation_grace_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("token_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_sessions_token_digest_format")),
        sa.CheckConstraint("csrf_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_sessions_csrf_digest_format")),
        sa.CheckConstraint("idle_expires_at > created_at", name=op.f("ck_sessions_idle_expiry_after_creation")),
        sa.CheckConstraint("absolute_expires_at > created_at", name=op.f("ck_sessions_absolute_expiry_after_creation")),
        sa.CheckConstraint(
            "idle_expires_at <= absolute_expires_at", name=op.f("ck_sessions_idle_before_absolute_expiry")
        ),
        sa.CheckConstraint("last_seen_at >= created_at", name=op.f("ck_sessions_last_seen_ordered")),
        sa.CheckConstraint("rotated_at >= created_at", name=op.f("ck_sessions_rotated_ordered")),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name=op.f("ck_sessions_revoked_ordered")),
        sa.CheckConstraint(
            "replaced_at IS NULL OR replaced_at >= created_at", name=op.f("ck_sessions_replaced_ordered")
        ),
        sa.CheckConstraint(
            "rotation_grace_expires_at IS NULL OR rotation_grace_expires_at > replaced_at",
            name=op.f("ck_sessions_rotation_grace_ordered"),
        ),
        _owner_fk("sessions"),
        sa.PrimaryKeyConstraint("session_id", name="pk_sessions"),
        sa.UniqueConstraint("token_digest", name="uq_sessions_token_digest"),
        schema="nexora",
    )
    op.create_index("ix_sessions_owner_id", "sessions", ["owner_id"], schema="nexora")
    op.create_index(
        "ix_sessions_active",
        "sessions",
        ["owner_id", "revoked_at", "idle_expires_at", "absolute_expires_at"],
        schema="nexora",
    )

    op.create_table(
        "service_tokens",
        sa.Column("service_token_id", sa.Uuid(), nullable=False),
        sa.Column("principal", sa.String(32), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("principal = 'trd_bot_integration'", name=op.f("ck_service_tokens_principal_allowed")),
        sa.CheckConstraint("token_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_service_tokens_token_digest_format")),
        sa.CheckConstraint("jsonb_typeof(scopes) = 'array'", name=op.f("ck_service_tokens_scopes_array")),
        sa.CheckConstraint("expires_at > created_at", name=op.f("ck_service_tokens_expires_after_creation")),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at", name=op.f("ck_service_tokens_revoked_ordered")
        ),
        sa.PrimaryKeyConstraint("service_token_id", name="pk_service_tokens"),
        sa.UniqueConstraint("token_digest", name="uq_service_tokens_token_digest"),
        schema="nexora",
    )

    op.create_table(
        "security_audit_events",
        sa.Column("event_id", sa.String(68), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("target_type", sa.String(80), nullable=False),
        sa.Column("target_id", sa.String(160), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("source_class", sa.String(24), nullable=False),
        sa.Column("ip_address_hmac", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.CheckConstraint("char_length(event_type) > 0", name=op.f("ck_security_audit_events_event_type_nonempty")),
        sa.CheckConstraint(
            "actor_type IN ('owner', 'service', 'system', 'unknown')",
            name=op.f("ck_security_audit_events_actor_type_allowed"),
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'failure', 'denied')",
            name=op.f("ck_security_audit_events_outcome_allowed"),
        ),
        sa.CheckConstraint(
            "reason_code ~ '^[A-Z][A-Z0-9_]{2,79}$'",
            name=op.f("ck_security_audit_events_reason_code_format"),
        ),
        sa.CheckConstraint(
            "source_class IN ('loopback', 'private_overlay', 'internal_service', 'unknown')",
            name=op.f("ck_security_audit_events_source_class_allowed"),
        ),
        sa.CheckConstraint(
            "ip_address_hmac IS NULL OR ip_address_hmac ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_security_audit_events_ip_address_hmac_format"),
        ),
        sa.CheckConstraint("jsonb_typeof(metadata) = 'object'", name=op.f("ck_security_audit_events_metadata_object")),
        sa.PrimaryKeyConstraint("event_id", name="pk_security_audit_events"),
        schema="nexora",
    )
    op.create_index(
        "ix_security_audit_events_correlation_id",
        "security_audit_events",
        ["correlation_id"],
        schema="nexora",
    )
    op.execute(
        """
        CREATE FUNCTION nexora.reject_security_audit_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'immutable Nexora security audit event cannot be changed';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER security_audit_events_immutable
        BEFORE UPDATE OR DELETE ON nexora.security_audit_events
        FOR EACH ROW EXECUTE FUNCTION nexora.reject_security_audit_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER security_audit_events_immutable ON nexora.security_audit_events")
    op.execute("DROP FUNCTION nexora.reject_security_audit_mutation()")
    op.drop_index("ix_security_audit_events_correlation_id", table_name="security_audit_events", schema="nexora")
    op.drop_table("security_audit_events", schema="nexora")
    op.drop_table("service_tokens", schema="nexora")
    op.drop_index("ix_sessions_active", table_name="sessions", schema="nexora")
    op.drop_index("ix_sessions_owner_id", table_name="sessions", schema="nexora")
    op.drop_table("sessions", schema="nexora")
    op.drop_index("ix_recovery_codes_owner_id", table_name="recovery_codes", schema="nexora")
    op.drop_table("recovery_codes", schema="nexora")
    op.drop_table("bootstrap_tokens", schema="nexora")
    op.drop_index("ix_webauthn_challenges_owner_id", table_name="webauthn_challenges", schema="nexora")
    op.drop_table("webauthn_challenges", schema="nexora")
    op.drop_index("ix_webauthn_credentials_owner_id", table_name="webauthn_credentials", schema="nexora")
    op.drop_table("webauthn_credentials", schema="nexora")
