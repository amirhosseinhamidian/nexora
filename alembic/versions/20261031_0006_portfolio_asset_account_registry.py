"""Create the owner-scoped portfolio, asset, and account registry.

Revision ID: 20261031_0006
Revises: 20261027_0005
Create Date: 2026-10-31 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261031_0006"
down_revision: str | None = "20261027_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("asset_key", sa.String(length=80), nullable=False),
        sa.Column("symbol", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("asset_class", sa.String(length=16), nullable=False),
        sa.Column("precision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "asset_class IN ('crypto', 'fiat', 'equity', 'fund', 'commodity', 'other')",
            name=op.f("ck_assets_asset_class_allowed"),
        ),
        sa.CheckConstraint(
            "asset_key ~ '^[a-z0-9]+([-_][a-z0-9]+)*$'",
            name=op.f("ck_assets_asset_key_format"),
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 120", name=op.f("ck_assets_name_length")),
        sa.CheckConstraint("precision BETWEEN 0 AND 30", name=op.f("ck_assets_precision_bounded")),
        sa.CheckConstraint("row_version >= 1", name=op.f("ck_assets_row_version_positive")),
        sa.CheckConstraint("status IN ('active', 'inactive')", name=op.f("ck_assets_status_allowed")),
        sa.CheckConstraint(
            "(status = 'active' AND deactivated_at IS NULL) OR (status = 'inactive' AND deactivated_at IS NOT NULL)",
            name=op.f("ck_assets_status_shape"),
        ),
        sa.CheckConstraint("symbol ~ '^[A-Z0-9][A-Z0-9._-]{0,23}$'", name=op.f("ck_assets_symbol_format")),
        sa.CheckConstraint("updated_at >= created_at", name=op.f("ck_assets_timestamps_ordered")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_assets_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("asset_id", name=op.f("pk_assets")),
        sa.UniqueConstraint("owner_id", "asset_id", name=op.f("uq_assets_owner_asset")),
        sa.UniqueConstraint("owner_id", "asset_key", name=op.f("uq_assets_owner_key")),
        schema="nexora",
    )
    op.create_index(op.f("ix_assets_owner_id"), "assets", ["owner_id"], schema="nexora")

    op.create_table(
        "asset_identifiers",
        sa.Column("asset_identifier_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("scheme", sa.String(length=24), nullable=False),
        sa.Column("value", sa.String(length=160), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "scheme IN ('iso_4217', 'ticker', 'coingecko', 'isin', 'cusip', 'figi', 'manual')",
            name=op.f("ck_asset_identifiers_scheme_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(value) BETWEEN 1 AND 160",
            name=op.f("ck_asset_identifiers_value_length"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "asset_id"],
            ["nexora.assets.owner_id", "nexora.assets.asset_id"],
            name=op.f("fk_asset_identifiers_owner_asset"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("asset_identifier_id", name=op.f("pk_asset_identifiers")),
        sa.UniqueConstraint(
            "owner_id",
            "asset_id",
            "scheme",
            name=op.f("uq_asset_identifiers_owner_asset_scheme"),
        ),
        sa.UniqueConstraint(
            "owner_id",
            "scheme",
            "value",
            name=op.f("uq_asset_identifiers_owner_scheme_value"),
        ),
        schema="nexora",
    )
    op.create_index(op.f("ix_asset_identifiers_asset_id"), "asset_identifiers", ["asset_id"], schema="nexora")
    op.create_index(op.f("ix_asset_identifiers_owner_id"), "asset_identifiers", ["owner_id"], schema="nexora")

    op.create_table(
        "portfolios",
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("base_asset_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('personal', 'paper', 'shadow')", name=op.f("ck_portfolios_kind_allowed")),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 120", name=op.f("ck_portfolios_name_length")),
        sa.CheckConstraint(
            "portfolio_key ~ '^[a-z0-9]+([-_][a-z0-9]+)*$'",
            name=op.f("ck_portfolios_portfolio_key_format"),
        ),
        sa.CheckConstraint("row_version >= 1", name=op.f("ck_portfolios_row_version_positive")),
        sa.CheckConstraint("status IN ('active', 'archived')", name=op.f("ck_portfolios_status_allowed")),
        sa.CheckConstraint(
            "(status = 'active' AND archived_at IS NULL) OR (status = 'archived' AND archived_at IS NOT NULL)",
            name=op.f("ck_portfolios_status_shape"),
        ),
        sa.CheckConstraint("updated_at >= created_at", name=op.f("ck_portfolios_timestamps_ordered")),
        sa.ForeignKeyConstraint(
            ["owner_id", "base_asset_id"],
            ["nexora.assets.owner_id", "nexora.assets.asset_id"],
            name=op.f("fk_portfolios_owner_base_asset"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_portfolios_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("portfolio_id", name=op.f("pk_portfolios")),
        sa.UniqueConstraint("owner_id", "portfolio_id", name=op.f("uq_portfolios_owner_portfolio")),
        sa.UniqueConstraint("owner_id", "portfolio_key", name=op.f("uq_portfolios_owner_key")),
        schema="nexora",
    )
    op.create_index(op.f("ix_portfolios_owner_id"), "portfolios", ["owner_id"], schema="nexora")

    op.create_table(
        "accounts",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("account_key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("institution_name", sa.String(length=120), nullable=True),
        sa.Column("external_reference", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "account_key ~ '^[a-z0-9]+([-_][a-z0-9]+)*$'",
            name=op.f("ck_accounts_account_key_format"),
        ),
        sa.CheckConstraint(
            "kind IN ('exchange', 'wallet_watch_only', 'cash', 'brokerage_manual', 'paper', 'shadow', 'other_manual')",
            name=op.f("ck_accounts_kind_allowed"),
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 120", name=op.f("ck_accounts_name_length")),
        sa.CheckConstraint("row_version >= 1", name=op.f("ck_accounts_row_version_positive")),
        sa.CheckConstraint("status IN ('active', 'closed')", name=op.f("ck_accounts_status_allowed")),
        sa.CheckConstraint(
            "(status = 'active' AND closed_at IS NULL) OR (status = 'closed' AND closed_at IS NOT NULL)",
            name=op.f("ck_accounts_status_shape"),
        ),
        sa.CheckConstraint("updated_at >= created_at", name=op.f("ck_accounts_timestamps_ordered")),
        sa.ForeignKeyConstraint(
            ["owner_id", "portfolio_id"],
            ["nexora.portfolios.owner_id", "nexora.portfolios.portfolio_id"],
            name=op.f("fk_accounts_owner_portfolio"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_accounts_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("account_id", name=op.f("pk_accounts")),
        sa.UniqueConstraint("owner_id", "account_key", name=op.f("uq_accounts_owner_key")),
        schema="nexora",
    )
    op.create_index(op.f("ix_accounts_owner_id"), "accounts", ["owner_id"], schema="nexora")
    op.create_index(op.f("ix_accounts_portfolio_id"), "accounts", ["portfolio_id"], schema="nexora")


def downgrade() -> None:
    op.drop_index(op.f("ix_accounts_portfolio_id"), table_name="accounts", schema="nexora")
    op.drop_index(op.f("ix_accounts_owner_id"), table_name="accounts", schema="nexora")
    op.drop_table("accounts", schema="nexora")
    op.drop_index(op.f("ix_portfolios_owner_id"), table_name="portfolios", schema="nexora")
    op.drop_table("portfolios", schema="nexora")
    op.drop_index(op.f("ix_asset_identifiers_owner_id"), table_name="asset_identifiers", schema="nexora")
    op.drop_index(op.f("ix_asset_identifiers_asset_id"), table_name="asset_identifiers", schema="nexora")
    op.drop_table("asset_identifiers", schema="nexora")
    op.drop_index(op.f("ix_assets_owner_id"), table_name="assets", schema="nexora")
    op.drop_table("assets", schema="nexora")
