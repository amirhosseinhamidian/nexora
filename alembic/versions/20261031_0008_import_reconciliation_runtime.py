"""Add bounded import and reconciliation evidence.

Revision ID: 20261031_0008
Revises: 20261031_0007
Create Date: 2026-10-31 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261031_0008"
down_revision: str | None = "20261031_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("source_format", sa.String(length=24), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("ready_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("quarantined_count", sa.Integer(), nullable=False),
        sa.Column("review_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_format IN ('csv', 'nexora_json')", name=op.f("ck_import_batches_source_format_allowed")
        ),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_import_batches_content_sha256_format")),
        sa.CheckConstraint(
            "status IN ('dry_run', 'reviewed', 'published', 'quarantined')",
            name=op.f("ck_import_batches_status_allowed"),
        ),
        sa.CheckConstraint("row_count BETWEEN 1 AND 5000", name=op.f("ck_import_batches_row_count_bounded")),
        sa.CheckConstraint(
            "ready_count >= 0 AND duplicate_count >= 0 AND quarantined_count >= 0",
            name=op.f("ck_import_batches_counts_positive"),
        ),
        sa.CheckConstraint(
            "ready_count + duplicate_count + quarantined_count = row_count",
            name=op.f("ck_import_batches_counts_complete"),
        ),
        sa.CheckConstraint(
            "review_reason IS NULL OR char_length(review_reason) BETWEEN 8 AND 500",
            name=op.f("ck_import_batches_review_reason_length"),
        ),
        sa.CheckConstraint(
            "(status = 'dry_run' AND reviewed_at IS NULL AND published_at IS NULL) OR "
            "(status = 'quarantined' AND reviewed_at IS NULL AND published_at IS NULL) OR "
            "(status = 'reviewed' AND reviewed_at IS NOT NULL AND published_at IS NULL) OR "
            "(status = 'published' AND reviewed_at IS NOT NULL AND published_at IS NOT NULL)",
            name=op.f("ck_import_batches_status_timestamps_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_import_batches_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("import_batch_id", name=op.f("pk_import_batches")),
        sa.UniqueConstraint("owner_id", "content_sha256", name=op.f("uq_import_batches_owner_content")),
        sa.UniqueConstraint("owner_id", "import_batch_id", name=op.f("uq_import_batches_owner_batch")),
        schema="nexora",
    )
    op.create_index(op.f("ix_import_batches_owner_id"), "import_batches", ["owner_id"], schema="nexora")

    op.create_table(
        "import_rows",
        sa.Column("import_row_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("external_row_id", sa.String(length=160), nullable=True),
        sa.Column("fingerprint_sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.Column("normalized_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("row_number BETWEEN 1 AND 5000", name=op.f("ck_import_rows_row_number_bounded")),
        sa.CheckConstraint(
            "external_row_id IS NULL OR char_length(external_row_id) BETWEEN 1 AND 160",
            name=op.f("ck_import_rows_external_row_id_length"),
        ),
        sa.CheckConstraint(
            "fingerprint_sha256 IS NULL OR fingerprint_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_import_rows_fingerprint_format"),
        ),
        sa.CheckConstraint(
            "status IN ('ready', 'duplicate', 'quarantined', 'published')", name=op.f("ck_import_rows_status_allowed")
        ),
        sa.CheckConstraint(
            "(status IN ('ready', 'published') AND normalized_payload IS NOT NULL "
            "AND fingerprint_sha256 IS NOT NULL AND reason_code IS NULL) OR "
            "(status IN ('duplicate', 'quarantined') AND reason_code IS NOT NULL)",
            name=op.f("ck_import_rows_status_evidence_shape"),
        ),
        sa.CheckConstraint(
            "normalized_payload IS NULL OR jsonb_typeof(normalized_payload) = 'object'",
            name=op.f("ck_import_rows_payload_object"),
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code ~ '^[A-Z][A-Z0-9_]{2,79}$'",
            name=op.f("ck_import_rows_reason_code_format"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_import_rows_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "import_batch_id"],
            ["nexora.import_batches.owner_id", "nexora.import_batches.import_batch_id"],
            name=op.f("fk_import_rows_owner_batch"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("import_row_id", name=op.f("pk_import_rows")),
        sa.UniqueConstraint("owner_id", "import_batch_id", "row_number", name=op.f("uq_import_rows_owner_batch_row")),
        sa.UniqueConstraint("owner_id", "import_row_id", name=op.f("uq_import_rows_owner_row")),
        schema="nexora",
    )
    op.create_index(op.f("ix_import_rows_import_batch_id"), "import_rows", ["import_batch_id"], schema="nexora")
    op.create_index(op.f("ix_import_rows_owner_id"), "import_rows", ["owner_id"], schema="nexora")
    op.create_index(
        op.f("ix_import_rows_owner_fingerprint"), "import_rows", ["owner_id", "fingerprint_sha256"], schema="nexora"
    )

    op.create_table(
        "reconciliation_cases",
        sa.Column("reconciliation_case_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("import_row_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("difference_code", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('open', 'matched', 'accepted_difference', 'resolved', 'ignored_with_reason')",
            name=op.f("ck_reconciliation_cases_state_allowed"),
        ),
        sa.CheckConstraint(
            "difference_code ~ '^[A-Z][A-Z0-9_]{2,79}$'", name=op.f("ck_reconciliation_cases_difference_code_format")
        ),
        sa.CheckConstraint(
            "reason IS NULL OR char_length(reason) BETWEEN 8 AND 500",
            name=op.f("ck_reconciliation_cases_reason_length"),
        ),
        sa.CheckConstraint("row_version >= 1", name=op.f("ck_reconciliation_cases_row_version_positive")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_reconciliation_cases_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "import_batch_id"],
            ["nexora.import_batches.owner_id", "nexora.import_batches.import_batch_id"],
            name=op.f("fk_reconciliation_cases_owner_batch"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "import_row_id"],
            ["nexora.import_rows.owner_id", "nexora.import_rows.import_row_id"],
            name=op.f("fk_reconciliation_cases_owner_row"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "transaction_id"],
            ["nexora.transactions.owner_id", "nexora.transactions.transaction_id"],
            name=op.f("fk_reconciliation_cases_owner_transaction"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("reconciliation_case_id", name=op.f("pk_reconciliation_cases")),
        sa.UniqueConstraint("owner_id", "import_row_id", name=op.f("uq_reconciliation_cases_owner_row")),
        sa.UniqueConstraint("owner_id", "reconciliation_case_id", name=op.f("uq_reconciliation_cases_owner_case")),
        schema="nexora",
    )
    op.create_index(op.f("ix_reconciliation_cases_owner_id"), "reconciliation_cases", ["owner_id"], schema="nexora")

    op.create_table(
        "reconciliation_decisions",
        sa.Column("reconciliation_decision_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("reconciliation_case_id", sa.Uuid(), nullable=False),
        sa.Column("from_state", sa.String(length=24), nullable=False),
        sa.Column("to_state", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "from_state IN ('open', 'matched', 'accepted_difference', 'resolved', 'ignored_with_reason')",
            name=op.f("ck_reconciliation_decisions_from_state_allowed"),
        ),
        sa.CheckConstraint(
            "to_state IN ('matched', 'accepted_difference', 'resolved', 'ignored_with_reason')",
            name=op.f("ck_reconciliation_decisions_to_state_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(reason) BETWEEN 8 AND 500", name=op.f("ck_reconciliation_decisions_reason_length")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_reconciliation_decisions_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "reconciliation_case_id"],
            ["nexora.reconciliation_cases.owner_id", "nexora.reconciliation_cases.reconciliation_case_id"],
            name=op.f("fk_reconciliation_decisions_owner_case"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("reconciliation_decision_id", name=op.f("pk_reconciliation_decisions")),
        sa.UniqueConstraint(
            "owner_id", "reconciliation_decision_id", name=op.f("uq_reconciliation_decisions_owner_decision")
        ),
        schema="nexora",
    )
    op.create_index(
        op.f("ix_reconciliation_decisions_owner_id"), "reconciliation_decisions", ["owner_id"], schema="nexora"
    )
    op.create_index(
        op.f("ix_reconciliation_decisions_reconciliation_case_id"),
        "reconciliation_decisions",
        ["reconciliation_case_id"],
        schema="nexora",
    )
    op.execute(
        "CREATE TRIGGER trg_reconciliation_decisions_immutable BEFORE UPDATE OR DELETE ON "
        "nexora.reconciliation_decisions FOR EACH ROW EXECUTE FUNCTION nexora.reject_transaction_journal_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_reconciliation_decisions_immutable ON nexora.reconciliation_decisions")
    op.drop_index(
        op.f("ix_reconciliation_decisions_reconciliation_case_id"),
        table_name="reconciliation_decisions",
        schema="nexora",
    )
    op.drop_index(op.f("ix_reconciliation_decisions_owner_id"), table_name="reconciliation_decisions", schema="nexora")
    op.drop_table("reconciliation_decisions", schema="nexora")
    op.drop_index(op.f("ix_reconciliation_cases_owner_id"), table_name="reconciliation_cases", schema="nexora")
    op.drop_table("reconciliation_cases", schema="nexora")
    op.drop_index(op.f("ix_import_rows_owner_fingerprint"), table_name="import_rows", schema="nexora")
    op.drop_index(op.f("ix_import_rows_owner_id"), table_name="import_rows", schema="nexora")
    op.drop_index(op.f("ix_import_rows_import_batch_id"), table_name="import_rows", schema="nexora")
    op.drop_table("import_rows", schema="nexora")
    op.drop_index(op.f("ix_import_batches_owner_id"), table_name="import_batches", schema="nexora")
    op.drop_table("import_batches", schema="nexora")
