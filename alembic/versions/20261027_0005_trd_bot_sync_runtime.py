"""Persist immutable TRD Bot synchronization receipts.

Revision ID: 20261027_0005
Revises: 20261026_0004
Create Date: 2026-10-27 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261027_0005"
down_revision: str | None = "20261026_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trd_bot_sync_receipts",
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=80), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload_schema", sa.String(length=160), nullable=False),
        sa.Column("provider_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.Column("envelope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("envelope_sha256", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(event_id) > 0", name=op.f("ck_trd_bot_sync_receipts_event_id_nonempty")),
        sa.CheckConstraint("char_length(event_type) > 0", name=op.f("ck_trd_bot_sync_receipts_event_type_nonempty")),
        sa.CheckConstraint(
            "char_length(payload_schema) > 0", name=op.f("ck_trd_bot_sync_receipts_payload_schema_nonempty")
        ),
        sa.CheckConstraint(
            "status IN ('applied', 'quarantined')", name=op.f("ck_trd_bot_sync_receipts_status_allowed")
        ),
        sa.CheckConstraint(
            "(status = 'applied' AND reason_code IS NULL) OR (status = 'quarantined' AND reason_code IS NOT NULL)",
            name=op.f("ck_trd_bot_sync_receipts_status_reason_shape"),
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code ~ '^[A-Z][A-Z0-9_]{2,79}$'",
            name=op.f("ck_trd_bot_sync_receipts_reason_code_format"),
        ),
        sa.CheckConstraint(
            "envelope_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_trd_bot_sync_receipts_envelope_sha256_format"),
        ),
        sa.CheckConstraint("jsonb_typeof(envelope) = 'object'", name=op.f("ck_trd_bot_sync_receipts_envelope_object")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name=op.f("fk_trd_bot_sync_receipts_owner_id_owner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("receipt_id", name=op.f("pk_trd_bot_sync_receipts")),
        sa.UniqueConstraint("owner_id", "event_id", name=op.f("uq_trd_bot_sync_receipts_owner_event")),
        schema="nexora",
    )
    op.create_index(
        op.f("ix_trd_bot_sync_receipts_owner_id"),
        "trd_bot_sync_receipts",
        ["owner_id"],
        unique=False,
        schema="nexora",
    )
    op.execute(
        """
        CREATE TRIGGER trd_bot_sync_receipts_immutable
        BEFORE UPDATE OR DELETE ON nexora.trd_bot_sync_receipts
        FOR EACH ROW EXECUTE FUNCTION nexora.reject_immutable_source_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trd_bot_sync_receipts_immutable ON nexora.trd_bot_sync_receipts")
    op.drop_index(
        op.f("ix_trd_bot_sync_receipts_owner_id"),
        table_name="trd_bot_sync_receipts",
        schema="nexora",
    )
    op.drop_table("trd_bot_sync_receipts", schema="nexora")
