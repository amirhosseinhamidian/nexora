"""Add rebuildable holdings, lots, cost-basis, and rejection evidence.

Revision ID: 20261101_0009
Revises: 20261031_0008
Create Date: 2026-11-01 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261101_0009"
down_revision: str | None = "20261031_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _owner_portfolio_foreign_key(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["owner_id", "portfolio_id"],
        ["nexora.portfolios.owner_id", "nexora.portfolios.portfolio_id"],
        name=op.f(name),
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "holdings_rebuilds",
        sa.Column("holdings_rebuild_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("cost_basis_method", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("projection_version", sa.String(length=64), nullable=False),
        sa.Column("journal_sha256", sa.String(length=64), nullable=False),
        sa.Column("journal_transaction_count", sa.Integer(), nullable=False),
        sa.Column("last_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.Column("rebuilt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "cost_basis_method IN ('fifo', 'weighted_average')",
            name=op.f("ck_holdings_rebuilds_cost_basis_method_allowed"),
        ),
        sa.CheckConstraint("status IN ('succeeded', 'rejected')", name=op.f("ck_holdings_rebuilds_status_allowed")),
        sa.CheckConstraint(
            "projection_version = 'nexora-holdings-projection-v1'",
            name=op.f("ck_holdings_rebuilds_projection_version_allowed"),
        ),
        sa.CheckConstraint(
            "journal_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_holdings_rebuilds_journal_sha256_format")
        ),
        sa.CheckConstraint(
            "journal_transaction_count >= 0",
            name=op.f("ck_holdings_rebuilds_journal_transaction_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "(status = 'succeeded' AND reason_code IS NULL) OR "
            "(status = 'rejected' AND reason_code = 'NEGATIVE_HOLDING_REJECTED')",
            name=op.f("ck_holdings_rebuilds_status_reason_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_holdings_rebuilds_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        _owner_portfolio_foreign_key("fk_holdings_rebuilds_owner_portfolio"),
        sa.PrimaryKeyConstraint("holdings_rebuild_id", name=op.f("pk_holdings_rebuilds")),
        sa.UniqueConstraint("owner_id", "holdings_rebuild_id", name=op.f("uq_holdings_rebuilds_owner_rebuild")),
        sa.UniqueConstraint(
            "owner_id",
            "portfolio_id",
            "cost_basis_method",
            "projection_version",
            "journal_sha256",
            name=op.f("uq_holdings_rebuilds_owner_snapshot"),
        ),
        schema="nexora",
    )
    op.create_index(op.f("ix_holdings_rebuilds_owner_id"), "holdings_rebuilds", ["owner_id"], schema="nexora")
    op.create_index(op.f("ix_holdings_rebuilds_portfolio_id"), "holdings_rebuilds", ["portfolio_id"], schema="nexora")

    op.create_table(
        "holding_projections",
        sa.Column("holding_projection_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("cost_basis_method", sa.String(length=24), nullable=False),
        sa.Column("quantity", sa.Numeric(60, 30), nullable=False),
        sa.Column("cost_basis_asset_id", sa.Uuid(), nullable=True),
        sa.Column("total_cost_basis", sa.Numeric(60, 30), nullable=True),
        sa.Column("average_unit_cost", sa.Numeric(60, 30), nullable=True),
        sa.Column("basis_status", sa.String(length=16), nullable=False),
        sa.Column("projection_version", sa.String(length=64), nullable=False),
        sa.Column("journal_sha256", sa.String(length=64), nullable=False),
        sa.Column("rebuilt_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "cost_basis_method IN ('fifo', 'weighted_average')",
            name=op.f("ck_holding_projections_cost_basis_method_allowed"),
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_holding_projections_quantity_positive")),
        sa.CheckConstraint(
            "basis_status IN ('known', 'unknown', 'mixed')",
            name=op.f("ck_holding_projections_basis_status_allowed"),
        ),
        sa.CheckConstraint(
            "(basis_status = 'known' AND cost_basis_asset_id IS NOT NULL AND total_cost_basis IS NOT NULL "
            "AND average_unit_cost IS NOT NULL) OR "
            "(basis_status IN ('unknown', 'mixed') AND cost_basis_asset_id IS NULL "
            "AND total_cost_basis IS NULL AND average_unit_cost IS NULL)",
            name=op.f("ck_holding_projections_basis_shape"),
        ),
        sa.CheckConstraint(
            "projection_version = 'nexora-holdings-projection-v1'",
            name=op.f("ck_holding_projections_projection_version_allowed"),
        ),
        sa.CheckConstraint(
            "journal_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_holding_projections_journal_sha256_format"),
        ),
        _owner_portfolio_foreign_key("fk_holding_projections_owner_portfolio"),
        sa.ForeignKeyConstraint(
            ["owner_id", "account_id"],
            ["nexora.accounts.owner_id", "nexora.accounts.account_id"],
            name=op.f("fk_holding_projections_owner_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "asset_id"],
            ["nexora.assets.owner_id", "nexora.assets.asset_id"],
            name=op.f("fk_holding_projections_owner_asset"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "cost_basis_asset_id"],
            ["nexora.assets.owner_id", "nexora.assets.asset_id"],
            name=op.f("fk_holding_projections_owner_basis_asset"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("holding_projection_id", name=op.f("pk_holding_projections")),
        sa.UniqueConstraint(
            "owner_id",
            "portfolio_id",
            "account_id",
            "asset_id",
            "cost_basis_method",
            name=op.f("uq_holding_projection"),
        ),
        schema="nexora",
    )
    op.create_index(op.f("ix_holding_projections_owner_id"), "holding_projections", ["owner_id"], schema="nexora")
    op.create_index(
        op.f("ix_holding_projections_portfolio_id"), "holding_projections", ["portfolio_id"], schema="nexora"
    )

    op.create_table(
        "lot_projections",
        sa.Column("lot_projection_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("cost_basis_method", sa.String(length=24), nullable=False),
        sa.Column("lot_key", sa.String(length=64), nullable=False),
        sa.Column("source_lot_key", sa.String(length=64), nullable=True),
        sa.Column("acquisition_transaction_id", sa.Uuid(), nullable=False),
        sa.Column("acquisition_leg_id", sa.Uuid(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_quantity", sa.Numeric(60, 30), nullable=False),
        sa.Column("remaining_quantity", sa.Numeric(60, 30), nullable=False),
        sa.Column("cost_basis_asset_id", sa.Uuid(), nullable=True),
        sa.Column("original_cost_basis", sa.Numeric(60, 30), nullable=True),
        sa.Column("remaining_cost_basis", sa.Numeric(60, 30), nullable=True),
        sa.Column("basis_status", sa.String(length=16), nullable=False),
        sa.Column("projection_version", sa.String(length=64), nullable=False),
        sa.Column("journal_sha256", sa.String(length=64), nullable=False),
        sa.Column("rebuilt_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("lot_key ~ '^[0-9a-f]{64}$'", name=op.f("ck_lot_projections_lot_key_format")),
        sa.CheckConstraint(
            "source_lot_key IS NULL OR source_lot_key ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_lot_projections_source_lot_key_format"),
        ),
        sa.CheckConstraint(
            "cost_basis_method IN ('fifo', 'weighted_average')",
            name=op.f("ck_lot_projections_cost_basis_method_allowed"),
        ),
        sa.CheckConstraint("original_quantity > 0", name=op.f("ck_lot_projections_original_quantity_positive")),
        sa.CheckConstraint(
            "remaining_quantity > 0 AND remaining_quantity <= original_quantity",
            name=op.f("ck_lot_projections_remaining_quantity_bounded"),
        ),
        sa.CheckConstraint(
            "basis_status IN ('known', 'unknown', 'mixed')",
            name=op.f("ck_lot_projections_basis_status_allowed"),
        ),
        sa.CheckConstraint(
            "(basis_status = 'known' AND cost_basis_asset_id IS NOT NULL AND original_cost_basis IS NOT NULL "
            "AND remaining_cost_basis IS NOT NULL) OR "
            "(basis_status IN ('unknown', 'mixed') AND cost_basis_asset_id IS NULL "
            "AND original_cost_basis IS NULL AND remaining_cost_basis IS NULL)",
            name=op.f("ck_lot_projections_basis_shape"),
        ),
        sa.CheckConstraint(
            "projection_version = 'nexora-holdings-projection-v1'",
            name=op.f("ck_lot_projections_projection_version_allowed"),
        ),
        sa.CheckConstraint("journal_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_lot_projections_journal_sha256_format")),
        _owner_portfolio_foreign_key("fk_lot_projections_owner_portfolio"),
        sa.ForeignKeyConstraint(
            ["owner_id", "account_id"],
            ["nexora.accounts.owner_id", "nexora.accounts.account_id"],
            name=op.f("fk_lot_projections_owner_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "asset_id"],
            ["nexora.assets.owner_id", "nexora.assets.asset_id"],
            name=op.f("fk_lot_projections_owner_asset"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "cost_basis_asset_id"],
            ["nexora.assets.owner_id", "nexora.assets.asset_id"],
            name=op.f("fk_lot_projections_owner_basis_asset"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("lot_projection_id", name=op.f("pk_lot_projections")),
        sa.UniqueConstraint("owner_id", "cost_basis_method", "lot_key", name=op.f("uq_lot_projection_key")),
        schema="nexora",
    )
    op.create_index(op.f("ix_lot_projections_owner_id"), "lot_projections", ["owner_id"], schema="nexora")
    op.create_index(op.f("ix_lot_projections_portfolio_id"), "lot_projections", ["portfolio_id"], schema="nexora")

    op.create_table(
        "lot_consumptions",
        sa.Column("lot_consumption_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("cost_basis_method", sa.String(length=24), nullable=False),
        sa.Column("consumption_key", sa.String(length=64), nullable=False),
        sa.Column("disposal_transaction_id", sa.Uuid(), nullable=False),
        sa.Column("disposal_leg_id", sa.Uuid(), nullable=False),
        sa.Column("lot_key", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Numeric(60, 30), nullable=False),
        sa.Column("cost_basis_asset_id", sa.Uuid(), nullable=True),
        sa.Column("allocated_cost_basis", sa.Numeric(60, 30), nullable=True),
        sa.Column("basis_status", sa.String(length=16), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("projection_version", sa.String(length=64), nullable=False),
        sa.Column("journal_sha256", sa.String(length=64), nullable=False),
        sa.Column("rebuilt_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "consumption_key ~ '^[0-9a-f]{64}$'", name=op.f("ck_lot_consumptions_consumption_key_format")
        ),
        sa.CheckConstraint(
            "cost_basis_method IN ('fifo', 'weighted_average')",
            name=op.f("ck_lot_consumptions_cost_basis_method_allowed"),
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_lot_consumptions_quantity_positive")),
        sa.CheckConstraint("sequence >= 1", name=op.f("ck_lot_consumptions_sequence_positive")),
        sa.CheckConstraint(
            "basis_status IN ('known', 'unknown', 'mixed')",
            name=op.f("ck_lot_consumptions_basis_status_allowed"),
        ),
        sa.CheckConstraint(
            "(basis_status = 'known' AND cost_basis_asset_id IS NOT NULL AND allocated_cost_basis IS NOT NULL) OR "
            "(basis_status IN ('unknown', 'mixed') AND cost_basis_asset_id IS NULL "
            "AND allocated_cost_basis IS NULL)",
            name=op.f("ck_lot_consumptions_basis_shape"),
        ),
        sa.CheckConstraint(
            "projection_version = 'nexora-holdings-projection-v1'",
            name=op.f("ck_lot_consumptions_projection_version_allowed"),
        ),
        sa.CheckConstraint("journal_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_lot_consumptions_journal_sha256_format")),
        _owner_portfolio_foreign_key("fk_lot_consumptions_owner_portfolio"),
        sa.ForeignKeyConstraint(
            ["owner_id", "cost_basis_asset_id"],
            ["nexora.assets.owner_id", "nexora.assets.asset_id"],
            name=op.f("fk_lot_consumptions_owner_basis_asset"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("lot_consumption_id", name=op.f("pk_lot_consumptions")),
        sa.UniqueConstraint("owner_id", "cost_basis_method", "consumption_key", name=op.f("uq_lot_consumption_key")),
        schema="nexora",
    )
    op.create_index(op.f("ix_lot_consumptions_owner_id"), "lot_consumptions", ["owner_id"], schema="nexora")
    op.create_index(op.f("ix_lot_consumptions_portfolio_id"), "lot_consumptions", ["portfolio_id"], schema="nexora")

    op.create_table(
        "holdings_rebuild_issues",
        sa.Column("holdings_rebuild_issue_id", sa.Uuid(), nullable=False),
        sa.Column("holdings_rebuild_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("cost_basis_method", sa.String(length=24), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_leg_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("requested_quantity", sa.Numeric(60, 30), nullable=False),
        sa.Column("available_quantity", sa.Numeric(60, 30), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("journal_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "reason_code = 'NEGATIVE_HOLDING_REJECTED'",
            name=op.f("ck_holdings_rebuild_issues_reason_code_allowed"),
        ),
        sa.CheckConstraint(
            "cost_basis_method IN ('fifo', 'weighted_average')",
            name=op.f("ck_holdings_rebuild_issues_cost_basis_method_allowed"),
        ),
        sa.CheckConstraint(
            "requested_quantity > 0", name=op.f("ck_holdings_rebuild_issues_requested_quantity_positive")
        ),
        sa.CheckConstraint(
            "available_quantity >= 0", name=op.f("ck_holdings_rebuild_issues_available_quantity_nonnegative")
        ),
        sa.CheckConstraint(
            "journal_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_holdings_rebuild_issues_journal_sha256_format"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "holdings_rebuild_id"],
            ["nexora.holdings_rebuilds.owner_id", "nexora.holdings_rebuilds.holdings_rebuild_id"],
            name=op.f("fk_holdings_rebuild_issues_owner_rebuild"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("holdings_rebuild_issue_id", name=op.f("pk_holdings_rebuild_issues")),
        sa.UniqueConstraint(
            "owner_id", "holdings_rebuild_issue_id", name=op.f("uq_holdings_rebuild_issues_owner_issue")
        ),
        schema="nexora",
    )
    op.create_index(
        op.f("ix_holdings_rebuild_issues_owner_id"), "holdings_rebuild_issues", ["owner_id"], schema="nexora"
    )
    op.execute(
        "CREATE TRIGGER trg_holdings_rebuild_issues_immutable BEFORE UPDATE OR DELETE ON "
        "nexora.holdings_rebuild_issues FOR EACH ROW EXECUTE FUNCTION nexora.reject_transaction_journal_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_holdings_rebuild_issues_immutable ON nexora.holdings_rebuild_issues")
    op.drop_index(op.f("ix_holdings_rebuild_issues_owner_id"), table_name="holdings_rebuild_issues", schema="nexora")
    op.drop_table("holdings_rebuild_issues", schema="nexora")
    op.drop_index(op.f("ix_lot_consumptions_portfolio_id"), table_name="lot_consumptions", schema="nexora")
    op.drop_index(op.f("ix_lot_consumptions_owner_id"), table_name="lot_consumptions", schema="nexora")
    op.drop_table("lot_consumptions", schema="nexora")
    op.drop_index(op.f("ix_lot_projections_portfolio_id"), table_name="lot_projections", schema="nexora")
    op.drop_index(op.f("ix_lot_projections_owner_id"), table_name="lot_projections", schema="nexora")
    op.drop_table("lot_projections", schema="nexora")
    op.drop_index(op.f("ix_holding_projections_portfolio_id"), table_name="holding_projections", schema="nexora")
    op.drop_index(op.f("ix_holding_projections_owner_id"), table_name="holding_projections", schema="nexora")
    op.drop_table("holding_projections", schema="nexora")
    op.drop_index(op.f("ix_holdings_rebuilds_portfolio_id"), table_name="holdings_rebuilds", schema="nexora")
    op.drop_index(op.f("ix_holdings_rebuilds_owner_id"), table_name="holdings_rebuilds", schema="nexora")
    op.drop_table("holdings_rebuilds", schema="nexora")
