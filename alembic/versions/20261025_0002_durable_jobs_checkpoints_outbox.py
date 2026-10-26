"""Add durable jobs, projection checkpoints, and transactional outbox.

Revision ID: 20261025_0002
Revises: 20261025_0001
Create Date: 2026-10-25 00:00:01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261025_0002"
down_revision: str | None = "20261025_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projection_checkpoints",
        sa.Column("checkpoint_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("consumer_name", sa.String(length=80), nullable=False),
        sa.Column("stream_name", sa.String(length=80), nullable=False),
        sa.Column("cursor", sa.String(length=512), nullable=True),
        sa.Column("last_event_id", sa.String(length=80), nullable=True),
        sa.Column("provider_version", sa.String(length=32), nullable=False),
        sa.Column("contract_version", sa.String(length=64), nullable=False),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(consumer_name) > 0", name="ck_projection_checkpoints_consumer_name_nonempty"),
        sa.CheckConstraint("char_length(stream_name) > 0", name="ck_projection_checkpoints_stream_name_nonempty"),
        sa.CheckConstraint(
            "cursor IS NULL OR char_length(cursor) > 0", name="ck_projection_checkpoints_cursor_nonempty"
        ),
        sa.CheckConstraint(
            "last_event_id IS NULL OR char_length(last_event_id) > 0",
            name="ck_projection_checkpoints_last_event_id_nonempty",
        ),
        sa.CheckConstraint(
            "char_length(provider_version) > 0", name="ck_projection_checkpoints_provider_version_nonempty"
        ),
        sa.CheckConstraint(
            "char_length(contract_version) > 0", name="ck_projection_checkpoints_contract_version_nonempty"
        ),
        sa.CheckConstraint("row_version >= 1", name="ck_projection_checkpoints_row_version_positive"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_projection_checkpoints_timestamps_ordered"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name="fk_projection_checkpoints_owner_id_owner_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("checkpoint_id", name="pk_projection_checkpoints"),
        sa.UniqueConstraint(
            "owner_id",
            "consumer_name",
            "stream_name",
            name="uq_projection_checkpoints_owner_consumer_stream",
        ),
        schema="nexora",
    )
    op.create_index(
        "ix_projection_checkpoints_owner_id",
        "projection_checkpoints",
        ["owner_id"],
        unique=False,
        schema="nexora",
    )
    op.create_table(
        "background_jobs",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="4", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("char_length(job_type) > 0", name="ck_background_jobs_job_type_nonempty"),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 16 AND 160",
            name="ck_background_jobs_idempotency_key_length",
        ),
        sa.CheckConstraint("idempotency_key !~ '[[:space:]]'", name="ck_background_jobs_idempotency_key_no_whitespace"),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_background_jobs_payload_object"),
        sa.CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_background_jobs_payload_sha256_format"),
        sa.CheckConstraint(
            "status IN ('queued', 'leased', 'retry_wait', 'succeeded', 'dead_letter')",
            name="ck_background_jobs_status_allowed",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts",
            name="ck_background_jobs_attempt_count_bounded",
        ),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 20", name="ck_background_jobs_max_attempts_bounded"),
        sa.CheckConstraint(
            "(status = 'leased' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(status IN ('queued', 'retry_wait') AND lease_owner IS NULL AND lease_expires_at IS NULL "
            "AND completed_at IS NULL) OR "
            "(status IN ('succeeded', 'dead_letter') AND lease_owner IS NULL AND lease_expires_at IS NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_background_jobs_status_shape",
        ),
        sa.CheckConstraint("updated_at >= created_at", name="ck_background_jobs_timestamps_ordered"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name="fk_background_jobs_owner_id_owner_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("job_id", name="pk_background_jobs"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_background_jobs_owner_idempotency_key"),
        sa.UniqueConstraint("owner_id", "job_id", name="uq_background_jobs_owner_job"),
        schema="nexora",
    )
    op.create_index("ix_background_jobs_owner_id", "background_jobs", ["owner_id"], schema="nexora")
    op.create_index(
        "ix_background_jobs_claim",
        "background_jobs",
        ["status", "available_at", "lease_expires_at", "created_at"],
        schema="nexora",
    )
    op.create_table(
        "outbox_events",
        sa.Column("outbox_event_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("background_job_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_id", sa.String(length=160), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="8", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("char_length(event_type) > 0", name="ck_outbox_events_event_type_nonempty"),
        sa.CheckConstraint("char_length(aggregate_type) > 0", name="ck_outbox_events_aggregate_type_nonempty"),
        sa.CheckConstraint("char_length(aggregate_id) > 0", name="ck_outbox_events_aggregate_id_nonempty"),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 16 AND 160",
            name="ck_outbox_events_idempotency_key_length",
        ),
        sa.CheckConstraint("idempotency_key !~ '[[:space:]]'", name="ck_outbox_events_idempotency_key_no_whitespace"),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_outbox_events_payload_object"),
        sa.CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_outbox_events_payload_sha256_format"),
        sa.CheckConstraint(
            "status IN ('pending', 'leased', 'published', 'dead_letter')",
            name="ck_outbox_events_status_allowed",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts",
            name="ck_outbox_events_attempt_count_bounded",
        ),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 20", name="ck_outbox_events_max_attempts_bounded"),
        sa.CheckConstraint(
            "(status = 'leased' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND published_at IS NULL) OR "
            "(status = 'pending' AND lease_owner IS NULL AND lease_expires_at IS NULL "
            "AND published_at IS NULL) OR "
            "(status = 'published' AND lease_owner IS NULL AND lease_expires_at IS NULL "
            "AND published_at IS NOT NULL) OR "
            "(status = 'dead_letter' AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name="ck_outbox_events_status_shape",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "background_job_id"],
            ["nexora.background_jobs.owner_id", "nexora.background_jobs.job_id"],
            name="fk_outbox_events_owner_job",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name="fk_outbox_events_owner_id_owner_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("outbox_event_id", name="pk_outbox_events"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_outbox_events_owner_idempotency_key"),
        schema="nexora",
    )
    op.create_index("ix_outbox_events_owner_id", "outbox_events", ["owner_id"], schema="nexora")
    op.create_index(
        "ix_outbox_events_claim",
        "outbox_events",
        ["status", "available_at", "lease_expires_at", "created_at"],
        schema="nexora",
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_claim", table_name="outbox_events", schema="nexora")
    op.drop_index("ix_outbox_events_owner_id", table_name="outbox_events", schema="nexora")
    op.drop_table("outbox_events", schema="nexora")
    op.drop_index("ix_background_jobs_claim", table_name="background_jobs", schema="nexora")
    op.drop_index("ix_background_jobs_owner_id", table_name="background_jobs", schema="nexora")
    op.drop_table("background_jobs", schema="nexora")
    op.drop_index("ix_projection_checkpoints_owner_id", table_name="projection_checkpoints", schema="nexora")
    op.drop_table("projection_checkpoints", schema="nexora")
