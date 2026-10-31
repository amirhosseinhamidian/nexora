"""Create the immutable owner-scoped transaction journal.

Revision ID: 20261031_0007
Revises: 20261031_0006
Create Date: 2026-10-31 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261031_0007"
down_revision: str | None = "20261031_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        op.f("uq_accounts_owner_account"),
        "accounts",
        ["owner_id", "account_id"],
        schema="nexora",
    )
    op.create_table(
        "transactions",
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_kind", sa.String(length=24), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("source_reference", sa.String(length=160), nullable=False),
        sa.Column("source_payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("memo", sa.String(length=500), nullable=True),
        sa.Column("correction_of_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("correction_kind", sa.String(length=16), nullable=True),
        sa.Column("correction_reason", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "transaction_kind IN ('buy', 'sell', 'deposit', 'withdrawal', 'transfer', 'fee', "
            "'income', 'reward', 'airdrop', 'adjustment', 'opening_balance')",
            name=op.f("ck_transactions_transaction_kind_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 16 AND 160",
            name=op.f("ck_transactions_idempotency_key_length"),
        ),
        sa.CheckConstraint(
            "idempotency_key !~ '[[:space:]]'",
            name=op.f("ck_transactions_idempotency_key_no_whitespace"),
        ),
        sa.CheckConstraint(
            "source_kind IN ('manual', 'import', 'trd_bot')",
            name=op.f("ck_transactions_source_kind_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(source_reference) BETWEEN 1 AND 160",
            name=op.f("ck_transactions_source_reference_length"),
        ),
        sa.CheckConstraint(
            "source_payload_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_transactions_source_payload_sha256_format"),
        ),
        sa.CheckConstraint(
            "request_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_transactions_request_sha256_format"),
        ),
        sa.CheckConstraint(
            "memo IS NULL OR char_length(memo) BETWEEN 1 AND 500",
            name=op.f("ck_transactions_memo_length"),
        ),
        sa.CheckConstraint(
            "(correction_kind IS NULL AND correction_of_transaction_id IS NULL AND correction_reason IS NULL) OR "
            "(correction_kind IN ('reversal', 'supersession') AND correction_of_transaction_id IS NOT NULL "
            "AND char_length(correction_reason) BETWEEN 8 AND 500)",
            name=op.f("ck_transactions_correction_shape"),
        ),
        sa.CheckConstraint(
            "correction_of_transaction_id IS NULL OR correction_of_transaction_id <> transaction_id",
            name=op.f("ck_transactions_no_self_correction"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "portfolio_id"],
            ["nexora.portfolios.owner_id", "nexora.portfolios.portfolio_id"],
            name=op.f("fk_transactions_owner_portfolio"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "correction_of_transaction_id"],
            ["nexora.transactions.owner_id", "nexora.transactions.transaction_id"],
            name=op.f("fk_transactions_owner_correction_target"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_transactions_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("transaction_id", name=op.f("pk_transactions")),
        sa.UniqueConstraint(
            "owner_id",
            "correction_of_transaction_id",
            name=op.f("uq_transactions_owner_correction_target"),
        ),
        sa.UniqueConstraint("owner_id", "idempotency_key", name=op.f("uq_transactions_owner_idempotency_key")),
        sa.UniqueConstraint("owner_id", "transaction_id", name=op.f("uq_transactions_owner_transaction")),
        schema="nexora",
    )
    op.create_index(op.f("ix_transactions_owner_id"), "transactions", ["owner_id"], schema="nexora")
    op.create_index(
        op.f("ix_transactions_owner_portfolio_occurred"),
        "transactions",
        ["owner_id", "portfolio_id", "occurred_at"],
        schema="nexora",
    )

    op.create_table(
        "transaction_legs",
        sa.Column("transaction_leg_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("external_counterparty", sa.String(length=160), nullable=True),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=60, scale=30), nullable=False),
        sa.Column("memo", sa.String(length=240), nullable=True),
        sa.CheckConstraint("sequence >= 1", name=op.f("ck_transaction_legs_sequence_positive")),
        sa.CheckConstraint("quantity <> 0", name=op.f("ck_transaction_legs_quantity_nonzero")),
        sa.CheckConstraint(
            "(account_id IS NOT NULL AND external_counterparty IS NULL) OR "
            "(account_id IS NULL AND char_length(external_counterparty) BETWEEN 1 AND 160)",
            name=op.f("ck_transaction_legs_account_boundary_shape"),
        ),
        sa.CheckConstraint(
            "memo IS NULL OR char_length(memo) BETWEEN 1 AND 240",
            name=op.f("ck_transaction_legs_memo_length"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "account_id"],
            ["nexora.accounts.owner_id", "nexora.accounts.account_id"],
            name=op.f("fk_transaction_legs_owner_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "asset_id"],
            ["nexora.assets.owner_id", "nexora.assets.asset_id"],
            name=op.f("fk_transaction_legs_owner_asset"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "transaction_id"],
            ["nexora.transactions.owner_id", "nexora.transactions.transaction_id"],
            name=op.f("fk_transaction_legs_owner_transaction"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_transaction_legs_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("transaction_leg_id", name=op.f("pk_transaction_legs")),
        sa.UniqueConstraint(
            "owner_id",
            "transaction_id",
            "sequence",
            name=op.f("uq_transaction_legs_owner_sequence"),
        ),
        schema="nexora",
    )
    op.create_index(
        op.f("ix_transaction_legs_owner_account"),
        "transaction_legs",
        ["owner_id", "account_id"],
        schema="nexora",
    )
    op.create_index(
        op.f("ix_transaction_legs_owner_asset"),
        "transaction_legs",
        ["owner_id", "asset_id"],
        schema="nexora",
    )
    op.create_index(op.f("ix_transaction_legs_owner_id"), "transaction_legs", ["owner_id"], schema="nexora")

    op.execute(
        """
        CREATE FUNCTION nexora.reject_transaction_journal_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'transaction journal rows are immutable'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    for table_name in ("transactions", "transaction_legs"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_immutable
            BEFORE UPDATE OR DELETE ON nexora.{table_name}
            FOR EACH ROW EXECUTE FUNCTION nexora.reject_transaction_journal_mutation()
            """
        )


def downgrade() -> None:
    for table_name in ("transaction_legs", "transactions"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable ON nexora.{table_name}")
    op.execute("DROP FUNCTION IF EXISTS nexora.reject_transaction_journal_mutation()")
    op.drop_index(op.f("ix_transaction_legs_owner_id"), table_name="transaction_legs", schema="nexora")
    op.drop_index(op.f("ix_transaction_legs_owner_asset"), table_name="transaction_legs", schema="nexora")
    op.drop_index(op.f("ix_transaction_legs_owner_account"), table_name="transaction_legs", schema="nexora")
    op.drop_table("transaction_legs", schema="nexora")
    op.drop_index(op.f("ix_transactions_owner_portfolio_occurred"), table_name="transactions", schema="nexora")
    op.drop_index(op.f("ix_transactions_owner_id"), table_name="transactions", schema="nexora")
    op.drop_table("transactions", schema="nexora")
    op.drop_constraint(op.f("uq_accounts_owner_account"), "accounts", schema="nexora", type_="unique")
