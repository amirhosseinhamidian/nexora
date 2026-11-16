"""Add immutable owner decision reviews and provider delivery state.

Revision ID: 20261116_0012
Revises: 20261112_0011
Create Date: 2026-11-16 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261116_0012"
down_revision: str | None = "20261112_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_review_states",
        sa.Column("review_state_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.String(length=160), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latest_review_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("current_version >= 0", name=op.f("ck_decision_review_states_current_version_nonnegative")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_decision_review_states_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("review_state_id", name=op.f("pk_decision_review_states")),
        sa.UniqueConstraint("owner_id", "decision_id", name=op.f("uq_decision_review_states_owner_decision")),
        schema="nexora",
    )
    op.create_index(
        op.f("ix_decision_review_states_owner_id"),
        "decision_review_states",
        ["owner_id"],
        schema="nexora",
    )
    op.create_table(
        "decision_reviews",
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.String(length=160), nullable=False),
        sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("portfolio_mode", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("reason_note", sa.String(length=500), nullable=True),
        sa.Column("evidence_generation", sa.Integer(), nullable=False),
        sa.Column("source_evidence_checksum", sa.String(length=71), nullable=False),
        sa.Column("source_reference", postgresql.JSONB(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revisit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_review_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("execution_authorization", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("transaction_created", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("order_intent_created", sa.Boolean(), server_default="false", nullable=False),
        sa.CheckConstraint("review_version >= 1", name=op.f("ck_decision_reviews_review_version_positive")),
        sa.CheckConstraint("action IN ('accept', 'reject', 'defer')", name=op.f("ck_decision_reviews_action_allowed")),
        sa.CheckConstraint(
            "portfolio_mode IN ('paper', 'shadow')", name=op.f("ck_decision_reviews_portfolio_mode_allowed")
        ),
        sa.CheckConstraint(
            "char_length(reason_code) BETWEEN 1 AND 100", name=op.f("ck_decision_reviews_reason_code_length")
        ),
        sa.CheckConstraint(
            "reason_note IS NULL OR char_length(reason_note) BETWEEN 1 AND 500",
            name=op.f("ck_decision_reviews_reason_note_length"),
        ),
        sa.CheckConstraint("evidence_generation >= 1", name=op.f("ck_decision_reviews_evidence_generation_positive")),
        sa.CheckConstraint(
            "source_evidence_checksum ~ '^sha256:[0-9a-f]{64}$'",
            name=op.f("ck_decision_reviews_evidence_checksum_format"),
        ),
        sa.CheckConstraint(
            "request_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_decision_reviews_request_checksum_format")
        ),
        sa.CheckConstraint("reviewed_at <= recorded_at", name=op.f("ck_decision_reviews_reviewed_before_recorded")),
        sa.CheckConstraint(
            "revisit_at IS NULL OR revisit_at > reviewed_at",
            name=op.f("ck_decision_reviews_revisit_after_review"),
        ),
        sa.CheckConstraint(
            "execution_authorization = false", name=op.f("ck_decision_reviews_no_execution_authorization")
        ),
        sa.CheckConstraint("transaction_created = false", name=op.f("ck_decision_reviews_no_transaction_created")),
        sa.CheckConstraint("order_intent_created = false", name=op.f("ck_decision_reviews_no_order_intent_created")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_decision_reviews_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "supersedes_review_id"],
            ["nexora.decision_reviews.owner_id", "nexora.decision_reviews.review_id"],
            name=op.f("fk_decision_reviews_owner_superseded_review"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("review_id", name=op.f("pk_decision_reviews")),
        sa.UniqueConstraint("owner_id", "review_id", name=op.f("uq_decision_reviews_owner_review")),
        sa.UniqueConstraint(
            "owner_id", "decision_id", "review_version", name=op.f("uq_decision_reviews_owner_decision_version")
        ),
        sa.UniqueConstraint("owner_id", "idempotency_key", name=op.f("uq_decision_reviews_owner_idempotency")),
        schema="nexora",
    )
    op.create_index(op.f("ix_decision_reviews_owner_id"), "decision_reviews", ["owner_id"], schema="nexora")
    op.create_index(
        "ix_decision_reviews_owner_decision_recorded",
        "decision_reviews",
        ["owner_id", "decision_id", "recorded_at"],
        schema="nexora",
    )
    op.create_foreign_key(
        "fk_decision_review_states_owner_latest_review",
        "decision_review_states",
        "decision_reviews",
        ["owner_id", "latest_review_id"],
        ["owner_id", "review_id"],
        source_schema="nexora",
        referent_schema="nexora",
        ondelete="RESTRICT",
    )
    op.create_table(
        "decision_review_deliveries",
        sa.Column("delivery_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("provider_command_id", sa.String(length=160), nullable=True),
        sa.Column("provider_correlation_id", sa.Uuid(), nullable=True),
        sa.Column("provider_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'duplicate')",
            name=op.f("ck_decision_review_deliveries_status_allowed"),
        ),
        sa.CheckConstraint("attempt_count >= 0", name=op.f("ck_decision_review_deliveries_attempt_count_nonnegative")),
        sa.ForeignKeyConstraint(
            ["owner_id", "review_id"],
            ["nexora.decision_reviews.owner_id", "nexora.decision_reviews.review_id"],
            name=op.f("fk_decision_review_deliveries_owner_review"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("delivery_id", name=op.f("pk_decision_review_deliveries")),
        sa.UniqueConstraint("owner_id", "review_id", name=op.f("uq_decision_review_deliveries_owner_review")),
        schema="nexora",
    )
    op.create_index(
        op.f("ix_decision_review_deliveries_owner_id"),
        "decision_review_deliveries",
        ["owner_id"],
        schema="nexora",
    )


def downgrade() -> None:
    op.drop_table("decision_review_deliveries", schema="nexora")
    op.drop_table("decision_review_states", schema="nexora")
    op.drop_table("decision_reviews", schema="nexora")
