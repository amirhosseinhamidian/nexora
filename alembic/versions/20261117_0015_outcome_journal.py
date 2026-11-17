"""Add append-only owner decision and outcome journal entries.

Revision ID: 20261117_0015
Revises: 20261117_0014
Create Date: 2026-11-17 18:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261117_0015"
down_revision: str | None = "20261117_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outcome_journal_entries",
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.String(length=160), nullable=False),
        sa.Column("entry_kind", sa.String(length=32), nullable=False),
        sa.Column("content", sa.String(length=4000), nullable=False),
        sa.Column("uncertainty_level", sa.String(length=16), nullable=False),
        sa.Column("uncertainty_note", sa.String(length=500), nullable=True),
        sa.Column("review_id", sa.Uuid(), nullable=True),
        sa.Column("portfolio_id", sa.Uuid(), nullable=True),
        sa.Column("simulated_position_reference", sa.String(length=160), nullable=True),
        sa.Column("decision_evidence_generation", sa.Integer(), nullable=False),
        sa.Column("decision_evidence_checksum", sa.String(length=71), nullable=False),
        sa.Column("decision_source_reference", postgresql.JSONB(), nullable=False),
        sa.Column("source_lineage", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("supersedes_entry_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("author_kind", sa.String(length=16), server_default="owner", nullable=False),
        sa.Column("ai_generated", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("provider_rewritable", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("execution_authorization", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("transaction_created", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("order_intent_created", sa.Boolean(), server_default="false", nullable=False),
        sa.CheckConstraint(
            "entry_kind IN ('owner_note', 'review_rationale', 'observed_outcome', "
            "'expectation_comparison', 'lesson', 'correction')",
            name=op.f("ck_outcome_journal_entries_entry_kind_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(decision_id) BETWEEN 1 AND 160",
            name=op.f("ck_outcome_journal_entries_decision_id_length"),
        ),
        sa.CheckConstraint(
            "char_length(content) BETWEEN 1 AND 4000",
            name=op.f("ck_outcome_journal_entries_content_length"),
        ),
        sa.CheckConstraint(
            "uncertainty_level IN ('low', 'medium', 'high', 'unknown')",
            name=op.f("ck_outcome_journal_entries_uncertainty_level_allowed"),
        ),
        sa.CheckConstraint(
            "uncertainty_note IS NULL OR char_length(uncertainty_note) BETWEEN 1 AND 500",
            name=op.f("ck_outcome_journal_entries_uncertainty_note_length"),
        ),
        sa.CheckConstraint(
            "simulated_position_reference IS NULL OR char_length(simulated_position_reference) BETWEEN 1 AND 160",
            name=op.f("ck_outcome_journal_entries_simulated_position_reference_length"),
        ),
        sa.CheckConstraint(
            "decision_evidence_generation >= 1",
            name=op.f("ck_outcome_journal_entries_decision_generation_positive"),
        ),
        sa.CheckConstraint(
            "decision_evidence_checksum ~ '^sha256:[0-9a-f]{64}$'",
            name=op.f("ck_outcome_journal_entries_decision_checksum_format"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(decision_source_reference) = 'object'",
            name=op.f("ck_outcome_journal_entries_decision_source_object"),
        ),
        sa.CheckConstraint(
            "decision_source_reference ->> 'schema_version' = 'nexora-source-reference-v1' AND "
            "decision_source_reference ->> 'source_product' = 'trd_bot' AND "
            "decision_source_reference ->> 'resource_type' = 'decision_evaluation' AND "
            "decision_source_reference ->> 'resource_id' = decision_id AND "
            "decision_source_reference ->> 'checksum' = decision_evidence_checksum AND "
            "(decision_source_reference ->> 'observed_at')::timestamptz <= occurred_at",
            name=op.f("ck_outcome_journal_entries_decision_source_matches_entry"),
        ),
        sa.CheckConstraint(
            "source_lineage IS NULL OR jsonb_typeof(source_lineage) = 'object'",
            name=op.f("ck_outcome_journal_entries_source_lineage_object"),
        ),
        sa.CheckConstraint(
            "source_lineage IS NULL OR ("
            "source_lineage ->> 'schema_version' = 'nexora-outcome-source-lineage-v1' AND "
            "char_length(source_lineage ->> 'source_id') BETWEEN 1 AND 160 AND "
            "source_lineage ->> 'source_kind' IN "
            "('provider_evidence', 'portfolio_snapshot', 'manual_observation', 'external_record') AND "
            "source_lineage ->> 'checksum' ~ '^sha256:[0-9a-f]{64}$' AND "
            "source_lineage ? 'observed_at' AND "
            "(source_lineage ->> 'observed_at')::timestamptz <= occurred_at)",
            name=op.f("ck_outcome_journal_entries_source_lineage_shape"),
        ),
        sa.CheckConstraint(
            "entry_kind <> 'observed_outcome' OR source_lineage IS NOT NULL",
            name=op.f("ck_outcome_journal_entries_observed_outcome_has_lineage"),
        ),
        sa.CheckConstraint(
            "(entry_kind = 'correction' AND supersedes_entry_id IS NOT NULL) OR "
            "(entry_kind <> 'correction' AND supersedes_entry_id IS NULL)",
            name=op.f("ck_outcome_journal_entries_correction_shape"),
        ),
        sa.CheckConstraint(
            "supersedes_entry_id IS NULL OR supersedes_entry_id <> entry_id",
            name=op.f("ck_outcome_journal_entries_no_self_correction"),
        ),
        sa.CheckConstraint(
            "occurred_at <= recorded_at",
            name=op.f("ck_outcome_journal_entries_occurred_before_recorded"),
        ),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 16 AND 160",
            name=op.f("ck_outcome_journal_entries_idempotency_key_length"),
        ),
        sa.CheckConstraint(
            "idempotency_key !~ '[[:space:]]'",
            name=op.f("ck_outcome_journal_entries_idempotency_key_no_whitespace"),
        ),
        sa.CheckConstraint(
            "request_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_outcome_journal_entries_request_checksum_format"),
        ),
        sa.CheckConstraint("author_kind = 'owner'", name=op.f("ck_outcome_journal_entries_owner_authored_only")),
        sa.CheckConstraint("ai_generated = false", name=op.f("ck_outcome_journal_entries_no_ai_generated_entry")),
        sa.CheckConstraint("provider_rewritable = false", name=op.f("ck_outcome_journal_entries_no_provider_rewrite")),
        sa.CheckConstraint(
            "execution_authorization = false",
            name=op.f("ck_outcome_journal_entries_no_execution_authorization"),
        ),
        sa.CheckConstraint(
            "transaction_created = false", name=op.f("ck_outcome_journal_entries_no_transaction_created")
        ),
        sa.CheckConstraint(
            "order_intent_created = false", name=op.f("ck_outcome_journal_entries_no_order_intent_created")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_outcome_journal_entries_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "review_id"],
            ["nexora.decision_reviews.owner_id", "nexora.decision_reviews.review_id"],
            name=op.f("fk_outcome_journal_entries_owner_review"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "portfolio_id"],
            ["nexora.portfolios.owner_id", "nexora.portfolios.portfolio_id"],
            name=op.f("fk_outcome_journal_entries_owner_portfolio"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "supersedes_entry_id"],
            ["nexora.outcome_journal_entries.owner_id", "nexora.outcome_journal_entries.entry_id"],
            name=op.f("fk_outcome_journal_entries_owner_superseded_entry"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("entry_id", name=op.f("pk_outcome_journal_entries")),
        sa.UniqueConstraint("owner_id", "entry_id", name=op.f("uq_outcome_journal_entries_owner_entry")),
        sa.UniqueConstraint("owner_id", "idempotency_key", name=op.f("uq_outcome_journal_entries_owner_idempotency")),
        sa.UniqueConstraint(
            "owner_id",
            "supersedes_entry_id",
            name=op.f("uq_outcome_journal_entries_owner_superseded_entry"),
        ),
        schema="nexora",
    )
    op.create_index(
        op.f("ix_outcome_journal_entries_owner_id"),
        "outcome_journal_entries",
        ["owner_id"],
        schema="nexora",
    )
    op.create_index(
        "ix_outcome_journal_entries_owner_decision_occurred",
        "outcome_journal_entries",
        ["owner_id", "decision_id", "occurred_at"],
        schema="nexora",
    )


def downgrade() -> None:
    op.drop_table("outcome_journal_entries", schema="nexora")
