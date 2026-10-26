"""Add durable recent-reauthentication evidence to browser sessions.

Revision ID: 20261026_0004
Revises: 20261026_0003
Create Date: 2026-10-26 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261026_0004"
down_revision: str | None = "20261026_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("reauthenticated_at", sa.DateTime(timezone=True), nullable=True),
        schema="nexora",
    )
    op.execute("UPDATE nexora.sessions SET reauthenticated_at = created_at WHERE reauthenticated_at IS NULL")
    op.alter_column("sessions", "reauthenticated_at", nullable=False, schema="nexora")
    op.create_check_constraint(
        op.f("ck_sessions_reauthenticated_ordered"),
        "sessions",
        "reauthenticated_at >= created_at",
        schema="nexora",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_sessions_reauthenticated_ordered"),
        "sessions",
        type_="check",
        schema="nexora",
    )
    op.drop_column("sessions", "reauthenticated_at", schema="nexora")
