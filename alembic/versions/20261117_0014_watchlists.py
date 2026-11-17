"""Add owner watchlists and bounded monitoring preferences.

Revision ID: 20261117_0014
Revises: 20261117_0013
Create Date: 2026-11-17 16:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261117_0014"
down_revision: str | None = "20261117_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watchlists",
        sa.Column("watchlist_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("row_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 120", name=op.f("ck_watchlists_name_length")),
        sa.CheckConstraint("row_version >= 0", name=op.f("ck_watchlists_row_version_nonnegative")),
        sa.CheckConstraint("updated_at >= created_at", name=op.f("ck_watchlists_timestamps_ordered")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_watchlists_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("watchlist_id", name=op.f("pk_watchlists")),
        sa.UniqueConstraint("owner_id", "watchlist_id", name=op.f("uq_watchlists_owner_watchlist")),
        sa.UniqueConstraint("owner_id", "name", name=op.f("uq_watchlists_owner_name")),
        schema="nexora",
    )
    op.create_index(op.f("ix_watchlists_owner_id"), "watchlists", ["owner_id"], schema="nexora")
    op.create_table(
        "watchlist_items",
        sa.Column("watchlist_item_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_id", sa.Uuid(), nullable=False),
        sa.Column("item_kind", sa.String(length=24), nullable=False),
        sa.Column("reference", sa.String(length=160), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "item_kind IN ('asset', 'market', 'strategy', 'candidate_source')",
            name=op.f("ck_watchlist_items_item_kind_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(reference) BETWEEN 1 AND 160",
            name=op.f("ck_watchlist_items_reference_length"),
        ),
        sa.CheckConstraint(
            "label IS NULL OR char_length(label) BETWEEN 1 AND 120",
            name=op.f("ck_watchlist_items_label_length"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "watchlist_id"],
            ["nexora.watchlists.owner_id", "nexora.watchlists.watchlist_id"],
            name=op.f("fk_watchlist_items_owner_watchlist"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("watchlist_item_id", name=op.f("pk_watchlist_items")),
        sa.UniqueConstraint(
            "owner_id",
            "watchlist_id",
            "item_kind",
            "reference",
            name=op.f("uq_watchlist_items_owner_watchlist_kind_reference"),
        ),
        schema="nexora",
    )
    op.create_index(op.f("ix_watchlist_items_owner_id"), "watchlist_items", ["owner_id"], schema="nexora")
    op.create_index(op.f("ix_watchlist_items_watchlist_id"), "watchlist_items", ["watchlist_id"], schema="nexora")
    op.create_table(
        "watchlist_preferences",
        sa.Column("preference_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_id", sa.Uuid(), nullable=False),
        sa.Column("presentation_order", sa.String(length=24), server_default="newest_first", nullable=False),
        sa.Column("minimum_severity", sa.String(length=16), server_default="info", nullable=False),
        sa.Column("include_resolved", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "presentation_order IN ('newest_first', 'oldest_first', 'severity_desc')",
            name=op.f("ck_watchlist_preferences_presentation_order_allowed"),
        ),
        sa.CheckConstraint(
            "minimum_severity IN ('info', 'warning', 'critical')",
            name=op.f("ck_watchlist_preferences_minimum_severity_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "watchlist_id"],
            ["nexora.watchlists.owner_id", "nexora.watchlists.watchlist_id"],
            name=op.f("fk_watchlist_preferences_owner_watchlist"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("preference_id", name=op.f("pk_watchlist_preferences")),
        sa.UniqueConstraint("owner_id", "watchlist_id", name=op.f("uq_watchlist_preferences_owner_watchlist")),
        schema="nexora",
    )
    op.create_index(op.f("ix_watchlist_preferences_owner_id"), "watchlist_preferences", ["owner_id"], schema="nexora")
    op.create_index(
        op.f("ix_watchlist_preferences_watchlist_id"),
        "watchlist_preferences",
        ["watchlist_id"],
        schema="nexora",
    )
    op.create_table(
        "watchlist_operations",
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_id", sa.Uuid(), nullable=False),
        sa.Column("operation_type", sa.String(length=24), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "operation_type IN ('create', 'add_item', 'update_preferences')",
            name=op.f("ck_watchlist_operations_operation_type_allowed"),
        ),
        sa.CheckConstraint(
            "aggregate_version >= 0", name=op.f("ck_watchlist_operations_aggregate_version_nonnegative")
        ),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 16 AND 160",
            name=op.f("ck_watchlist_operations_idempotency_key_length"),
        ),
        sa.CheckConstraint(
            "idempotency_key !~ '[[:space:]]'",
            name=op.f("ck_watchlist_operations_idempotency_key_no_whitespace"),
        ),
        sa.CheckConstraint(
            "request_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_watchlist_operations_request_checksum_format"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "watchlist_id"],
            ["nexora.watchlists.owner_id", "nexora.watchlists.watchlist_id"],
            name=op.f("fk_watchlist_operations_owner_watchlist"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("operation_id", name=op.f("pk_watchlist_operations")),
        sa.UniqueConstraint("owner_id", "idempotency_key", name=op.f("uq_watchlist_operations_owner_idempotency")),
        schema="nexora",
    )
    op.create_index(op.f("ix_watchlist_operations_owner_id"), "watchlist_operations", ["owner_id"], schema="nexora")
    op.create_index(
        op.f("ix_watchlist_operations_watchlist_id"),
        "watchlist_operations",
        ["watchlist_id"],
        schema="nexora",
    )


def downgrade() -> None:
    op.drop_table("watchlist_operations", schema="nexora")
    op.drop_table("watchlist_preferences", schema="nexora")
    op.drop_table("watchlist_items", schema="nexora")
    op.drop_table("watchlists", schema="nexora")
