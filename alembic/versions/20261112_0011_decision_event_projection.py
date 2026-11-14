"""Add durable owner-scoped decision and event projection.

Revision ID: 20261112_0011
Revises: 20261101_0010
Create Date: 2026-11-12 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261112_0011"
down_revision: str | None = "20261101_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_projection_states",
        sa.Column("projection_state_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="staging", nullable=False),
        sa.Column("trigger", sa.String(length=24), nullable=False),
        sa.Column("provider_version", sa.String(length=32), nullable=False),
        sa.Column("contract_version", sa.String(length=64), nullable=False),
        sa.Column("projection", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("resource_progress", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("aggregate_versions", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("quarantine", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("projection_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("generation >= 1", name=op.f("ck_decision_projection_states_generation_positive")),
        sa.CheckConstraint(
            "status IN ('staging', 'active', 'superseded', 'rejected')",
            name=op.f("ck_decision_projection_states_status_allowed"),
        ),
        sa.CheckConstraint(
            "trigger IN ('cursor_expired', 'aggregate_gap', 'checksum_mismatch')",
            name=op.f("ck_decision_projection_states_trigger_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(projection) = 'object'",
            name=op.f("ck_decision_projection_states_projection_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(resource_progress) = 'object'",
            name=op.f("ck_decision_projection_states_resource_progress_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(aggregate_versions) = 'object'",
            name=op.f("ck_decision_projection_states_aggregate_versions_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(quarantine) = 'array'",
            name=op.f("ck_decision_projection_states_quarantine_array"),
        ),
        sa.CheckConstraint(
            "projection_sha256 IS NULL OR projection_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_decision_projection_states_checksum_format"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_decision_projection_states_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("projection_state_id", name=op.f("pk_decision_projection_states")),
        sa.UniqueConstraint(
            "owner_id",
            "generation",
            name=op.f("uq_decision_projection_states_owner_generation"),
        ),
        schema="nexora",
    )
    op.create_index(
        op.f("ix_decision_projection_states_owner_id"),
        "decision_projection_states",
        ["owner_id"],
        schema="nexora",
    )
    op.create_index(
        "uq_decision_projection_states_owner_active",
        "decision_projection_states",
        ["owner_id"],
        unique=True,
        schema="nexora",
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_decision_projection_states_owner_active",
        table_name="decision_projection_states",
        schema="nexora",
    )
    op.drop_table("decision_projection_states", schema="nexora")
