"""Add immutable price, FX and manual valuation evidence.

Revision ID: 20261101_0010
Revises: 20261101_0009
Create Date: 2026-11-01 08:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261101_0010"
down_revision: str | None = "20261101_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _owner_asset_fk(local: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["owner_id", local],
        ["nexora.assets.owner_id", "nexora.assets.asset_id"],
        name=op.f(name),
        ondelete="RESTRICT",
    )


def _lineage_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("source_reference", sa.String(length=160), nullable=False),
        sa.Column("source_payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _lineage_constraints(table_name: str) -> list[sa.Constraint]:
    return [
        sa.CheckConstraint(
            "char_length(source_reference) BETWEEN 1 AND 160",
            name=op.f(f"ck_{table_name}_source_reference_length"),
        ),
        sa.CheckConstraint(
            "source_payload_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{table_name}_source_payload_sha256_format"),
        ),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 160",
            name=op.f(f"ck_{table_name}_idempotency_key_length"),
        ),
        sa.CheckConstraint(
            "request_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{table_name}_request_sha256_format"),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "price_observations",
        sa.Column("price_observation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("quote_asset_id", sa.Uuid(), nullable=False),
        sa.Column("price", sa.Numeric(60, 30), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        *_lineage_columns(),
        sa.CheckConstraint("price > 0", name=op.f("ck_price_observations_price_positive")),
        sa.CheckConstraint("asset_id <> quote_asset_id", name=op.f("ck_price_observations_asset_pair_distinct")),
        sa.CheckConstraint("valid_until > observed_at", name=op.f("ck_price_observations_validity_after_observation")),
        sa.CheckConstraint(
            "source_kind IN ('provider', 'import')",
            name=op.f("ck_price_observations_source_kind_allowed"),
        ),
        *_lineage_constraints("price_observations"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_price_observations_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        _owner_asset_fk("asset_id", "fk_price_observations_owner_asset"),
        _owner_asset_fk("quote_asset_id", "fk_price_observations_owner_quote_asset"),
        sa.PrimaryKeyConstraint("price_observation_id", name=op.f("pk_price_observations")),
        sa.UniqueConstraint("owner_id", "idempotency_key", name=op.f("uq_price_observations_owner_idempotency")),
        sa.UniqueConstraint("owner_id", "price_observation_id", name=op.f("uq_price_observations_owner_observation")),
        schema="nexora",
    )
    op.create_index(op.f("ix_price_observations_owner_id"), "price_observations", ["owner_id"], schema="nexora")
    op.create_index(
        "ix_price_observations_owner_pair_time",
        "price_observations",
        ["owner_id", "asset_id", "quote_asset_id", "observed_at"],
        schema="nexora",
    )

    op.create_table(
        "fx_rate_observations",
        sa.Column("fx_rate_observation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("base_asset_id", sa.Uuid(), nullable=False),
        sa.Column("quote_asset_id", sa.Uuid(), nullable=False),
        sa.Column("rate", sa.Numeric(60, 30), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        *_lineage_columns(),
        sa.CheckConstraint("rate > 0", name=op.f("ck_fx_rate_observations_rate_positive")),
        sa.CheckConstraint("base_asset_id <> quote_asset_id", name=op.f("ck_fx_rate_observations_asset_pair_distinct")),
        sa.CheckConstraint(
            "valid_until > observed_at", name=op.f("ck_fx_rate_observations_validity_after_observation")
        ),
        sa.CheckConstraint(
            "source_kind IN ('provider', 'import')",
            name=op.f("ck_fx_rate_observations_source_kind_allowed"),
        ),
        *_lineage_constraints("fx_rate_observations"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_fx_rate_observations_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        _owner_asset_fk("base_asset_id", "fk_fx_rate_observations_owner_base_asset"),
        _owner_asset_fk("quote_asset_id", "fk_fx_rate_observations_owner_quote_asset"),
        sa.PrimaryKeyConstraint("fx_rate_observation_id", name=op.f("pk_fx_rate_observations")),
        sa.UniqueConstraint("owner_id", "idempotency_key", name=op.f("uq_fx_rate_observations_owner_idempotency")),
        sa.UniqueConstraint(
            "owner_id", "fx_rate_observation_id", name=op.f("uq_fx_rate_observations_owner_observation")
        ),
        schema="nexora",
    )
    op.create_index(op.f("ix_fx_rate_observations_owner_id"), "fx_rate_observations", ["owner_id"], schema="nexora")
    op.create_index(
        "ix_fx_rate_observations_owner_pair_time",
        "fx_rate_observations",
        ["owner_id", "base_asset_id", "quote_asset_id", "observed_at"],
        schema="nexora",
    )

    op.create_table(
        "manual_valuations",
        sa.Column("manual_valuation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("quote_asset_id", sa.Uuid(), nullable=False),
        sa.Column("unit_value", sa.Numeric(60, 30), nullable=False),
        sa.Column("valued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        *_lineage_columns(),
        sa.CheckConstraint("unit_value > 0", name=op.f("ck_manual_valuations_unit_value_positive")),
        sa.CheckConstraint("asset_id <> quote_asset_id", name=op.f("ck_manual_valuations_asset_pair_distinct")),
        sa.CheckConstraint("valid_until > valued_at", name=op.f("ck_manual_valuations_validity_after_valuation")),
        sa.CheckConstraint("char_length(reason) BETWEEN 8 AND 500", name=op.f("ck_manual_valuations_reason_length")),
        *_lineage_constraints("manual_valuations"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_manual_valuations_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "portfolio_id"],
            ["nexora.portfolios.owner_id", "nexora.portfolios.portfolio_id"],
            name=op.f("fk_manual_valuations_owner_portfolio"),
            ondelete="RESTRICT",
        ),
        _owner_asset_fk("asset_id", "fk_manual_valuations_owner_asset"),
        _owner_asset_fk("quote_asset_id", "fk_manual_valuations_owner_quote_asset"),
        sa.PrimaryKeyConstraint("manual_valuation_id", name=op.f("pk_manual_valuations")),
        sa.UniqueConstraint("owner_id", "idempotency_key", name=op.f("uq_manual_valuations_owner_idempotency")),
        sa.UniqueConstraint("owner_id", "manual_valuation_id", name=op.f("uq_manual_valuations_owner_valuation")),
        schema="nexora",
    )
    op.create_index(op.f("ix_manual_valuations_owner_id"), "manual_valuations", ["owner_id"], schema="nexora")
    op.create_index(
        op.f("ix_manual_valuations_portfolio_id"),
        "manual_valuations",
        ["portfolio_id"],
        schema="nexora",
    )
    op.create_index(
        "ix_manual_valuations_owner_portfolio_pair_time",
        "manual_valuations",
        ["owner_id", "portfolio_id", "asset_id", "quote_asset_id", "valued_at"],
        schema="nexora",
    )

    for table_name in ("price_observations", "fx_rate_observations", "manual_valuations"):
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_immutable BEFORE UPDATE OR DELETE ON nexora.{table_name} "
            "FOR EACH ROW EXECUTE FUNCTION nexora.reject_transaction_journal_mutation()"
        )


def downgrade() -> None:
    for table_name in ("manual_valuations", "fx_rate_observations", "price_observations"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable ON nexora.{table_name}")
    op.drop_index("ix_manual_valuations_owner_portfolio_pair_time", table_name="manual_valuations", schema="nexora")
    op.drop_index(op.f("ix_manual_valuations_portfolio_id"), table_name="manual_valuations", schema="nexora")
    op.drop_index(op.f("ix_manual_valuations_owner_id"), table_name="manual_valuations", schema="nexora")
    op.drop_table("manual_valuations", schema="nexora")
    op.drop_index("ix_fx_rate_observations_owner_pair_time", table_name="fx_rate_observations", schema="nexora")
    op.drop_index(op.f("ix_fx_rate_observations_owner_id"), table_name="fx_rate_observations", schema="nexora")
    op.drop_table("fx_rate_observations", schema="nexora")
    op.drop_index("ix_price_observations_owner_pair_time", table_name="price_observations", schema="nexora")
    op.drop_index(op.f("ix_price_observations_owner_id"), table_name="price_observations", schema="nexora")
    op.drop_table("price_observations", schema="nexora")
