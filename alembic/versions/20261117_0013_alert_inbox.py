"""Add durable owner alert state history.

Revision ID: 20261117_0013
Revises: 20261116_0012
Create Date: 2026-11-17 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261117_0013"
down_revision: str | None = "20261116_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "owner_alert_states",
        sa.Column("alert_state_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("alert_id", sa.String(length=160), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latest_history_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("current_version >= 0", name=op.f("ck_owner_alert_states_current_version_nonnegative")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_owner_alert_states_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("alert_state_id", name=op.f("pk_owner_alert_states")),
        sa.UniqueConstraint("owner_id", "alert_id", name=op.f("uq_owner_alert_states_owner_alert")),
        schema="nexora",
    )
    op.create_index(op.f("ix_owner_alert_states_owner_id"), "owner_alert_states", ["owner_id"], schema="nexora")
    op.create_table(
        "alert_state_history",
        sa.Column("alert_history_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("alert_id", sa.String(length=160), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("snooze_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_generation", sa.Integer(), nullable=False),
        sa.Column("source_evidence_checksum", sa.String(length=71), nullable=False),
        sa.Column("source_reference", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.CheckConstraint("state_version >= 1", name=op.f("ck_alert_state_history_state_version_positive")),
        sa.CheckConstraint(
            "state IN ('open', 'acknowledged', 'snoozed', 'resolved', 'expired')",
            name=op.f("ck_alert_state_history_state_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(reason_code) BETWEEN 1 AND 100",
            name=op.f("ck_alert_state_history_reason_code_length"),
        ),
        sa.CheckConstraint(
            "evidence_generation >= 1",
            name=op.f("ck_alert_state_history_evidence_generation_positive"),
        ),
        sa.CheckConstraint(
            "source_evidence_checksum ~ '^sha256:[0-9a-f]{64}$'",
            name=op.f("ck_alert_state_history_evidence_checksum_format"),
        ),
        sa.CheckConstraint(
            "request_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_alert_state_history_request_checksum_format"),
        ),
        sa.CheckConstraint(
            "occurred_at <= recorded_at",
            name=op.f("ck_alert_state_history_occurred_before_recorded"),
        ),
        sa.CheckConstraint(
            "(state = 'snoozed' AND snooze_until IS NOT NULL) OR (state <> 'snoozed' AND snooze_until IS NULL)",
            name=op.f("ck_alert_state_history_snooze_until_matches_state"),
        ),
        sa.CheckConstraint(
            "snooze_until IS NULL OR snooze_until > occurred_at",
            name=op.f("ck_alert_state_history_snooze_until_after_occurrence"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_alert_state_history_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("alert_history_id", name=op.f("pk_alert_state_history")),
        sa.UniqueConstraint("owner_id", "alert_history_id", name=op.f("uq_alert_state_history_owner_history")),
        sa.UniqueConstraint(
            "owner_id", "alert_id", "state_version", name=op.f("uq_alert_state_history_owner_alert_version")
        ),
        sa.UniqueConstraint("owner_id", "idempotency_key", name=op.f("uq_alert_state_history_owner_idempotency")),
        schema="nexora",
    )
    op.create_index(op.f("ix_alert_state_history_owner_id"), "alert_state_history", ["owner_id"], schema="nexora")
    op.create_index(
        "ix_alert_state_history_owner_alert_recorded",
        "alert_state_history",
        ["owner_id", "alert_id", "recorded_at"],
        schema="nexora",
    )
    op.create_foreign_key(
        "fk_owner_alert_states_owner_latest_history",
        "owner_alert_states",
        "alert_state_history",
        ["owner_id", "latest_history_id"],
        ["owner_id", "alert_history_id"],
        source_schema="nexora",
        referent_schema="nexora",
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_table("owner_alert_states", schema="nexora")
    op.drop_table("alert_state_history", schema="nexora")
