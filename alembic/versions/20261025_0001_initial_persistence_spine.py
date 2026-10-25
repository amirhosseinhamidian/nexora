"""Create the owner-aware immutable persistence spine.

Revision ID: 20261025_0001
Revises:
Create Date: 2026-10-25 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261025_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SCHEMA nexora"))
    op.create_table(
        "owner_profiles",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("owner_key", sa.String(length=32), nullable=False),
        sa.Column("locale", sa.String(length=2), server_default="fa", nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="UTC", nullable=False),
        sa.Column("theme", sa.String(length=16), server_default="system", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("locale IN ('fa', 'en')", name="ck_owner_profiles_locale_allowed"),
        sa.CheckConstraint("owner_key = 'primary_owner'", name="ck_owner_profiles_owner_key_singleton"),
        sa.CheckConstraint("theme IN ('light', 'dark', 'system')", name="ck_owner_profiles_theme_allowed"),
        sa.CheckConstraint("char_length(timezone) > 0", name="ck_owner_profiles_timezone_nonempty"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_owner_profiles_timestamps_ordered"),
        sa.PrimaryKeyConstraint("owner_id", name="pk_owner_profiles"),
        sa.UniqueConstraint("owner_key", name="uq_owner_profiles_owner_key"),
        schema="nexora",
    )
    op.create_table(
        "source_references",
        sa.Column("source_reference_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_entity_type", sa.String(length=64), nullable=False),
        sa.Column("source_entity_id", sa.String(length=128), nullable=False),
        sa.Column("source_schema_version", sa.String(length=64), nullable=False),
        sa.Column("source_version", sa.String(length=64), nullable=False),
        sa.Column("source_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "payload_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_source_references_payload_sha256_format",
        ),
        sa.CheckConstraint(
            "char_length(source_entity_id) > 0",
            name="ck_source_references_source_entity_id_nonempty",
        ),
        sa.CheckConstraint(
            "char_length(source_entity_type) > 0",
            name="ck_source_references_source_entity_type_nonempty",
        ),
        sa.CheckConstraint(
            "char_length(source_schema_version) > 0",
            name="ck_source_references_source_schema_version_nonempty",
        ),
        sa.CheckConstraint("source_system = 'trd_bot'", name="ck_source_references_source_system_allowed"),
        sa.CheckConstraint(
            "char_length(source_version) > 0",
            name="ck_source_references_source_version_nonempty",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["nexora.owner_profiles.owner_id"],
            name="fk_source_references_owner_id_owner_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("source_reference_id", name="pk_source_references"),
        sa.UniqueConstraint(
            "owner_id",
            "source_reference_id",
            "payload_sha256",
            name="uq_source_references_owner_reference_checksum",
        ),
        sa.UniqueConstraint(
            "owner_id",
            "source_system",
            "source_entity_type",
            "source_entity_id",
            "source_version",
            name="uq_source_references_source_identity",
        ),
        schema="nexora",
    )
    op.create_index(
        "ix_source_references_owner_id",
        "source_references",
        ["owner_id"],
        unique=False,
        schema="nexora",
    )
    op.create_table(
        "immutable_source_evidence",
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("source_reference_id", sa.Uuid(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "payload_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_immutable_source_evidence_payload_sha256_format",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name="ck_immutable_source_evidence_payload_object",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "source_reference_id", "payload_sha256"],
            [
                "nexora.source_references.owner_id",
                "nexora.source_references.source_reference_id",
                "nexora.source_references.payload_sha256",
            ],
            name="fk_evidence_owner_reference_checksum",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("evidence_id", name="pk_immutable_source_evidence"),
        sa.UniqueConstraint(
            "source_reference_id",
            name="uq_immutable_source_evidence_source_reference_id",
        ),
        schema="nexora",
    )
    op.create_index(
        "ix_immutable_source_evidence_owner_id",
        "immutable_source_evidence",
        ["owner_id"],
        unique=False,
        schema="nexora",
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION nexora.reject_immutable_source_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'immutable Nexora source evidence cannot be updated or deleted';
            END;
            $$
            """
        )
    )
    for table in ("source_references", "immutable_source_evidence"):
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_{table}_immutable
                BEFORE UPDATE OR DELETE ON nexora.{table}
                FOR EACH ROW EXECUTE FUNCTION nexora.reject_immutable_source_mutation()
                """
            )
        )


def downgrade() -> None:
    op.drop_index(
        "ix_immutable_source_evidence_owner_id",
        table_name="immutable_source_evidence",
        schema="nexora",
    )
    op.drop_table("immutable_source_evidence", schema="nexora")
    op.drop_index("ix_source_references_owner_id", table_name="source_references", schema="nexora")
    op.drop_table("source_references", schema="nexora")
    op.drop_table("owner_profiles", schema="nexora")
    op.execute(sa.text("DROP FUNCTION nexora.reject_immutable_source_mutation()"))
    op.execute(sa.text("DROP SCHEMA nexora"))
