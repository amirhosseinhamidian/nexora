from __future__ import annotations

from nexora.adapters.postgresql import ALEMBIC_VERSION_SCHEMA, DATABASE_SESSION_OPTIONS, SCHEMA_NAME, Base
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable


def test_schema_contains_persistence_spine_and_durable_work_tables() -> None:
    assert set(Base.metadata.tables) == {
        "nexora.immutable_source_evidence",
        "nexora.owner_profiles",
        "nexora.projection_checkpoints",
        "nexora.background_jobs",
        "nexora.bootstrap_tokens",
        "nexora.outbox_events",
        "nexora.source_references",
        "nexora.recovery_codes",
        "nexora.security_audit_events",
        "nexora.service_tokens",
        "nexora.sessions",
        "nexora.webauthn_challenges",
        "nexora.webauthn_credentials",
        "nexora.trd_bot_sync_receipts",
    }
    assert all(table.schema == SCHEMA_NAME for table in Base.metadata.sorted_tables)


def test_database_namespace_cannot_become_the_implicit_search_path() -> None:
    assert ALEMBIC_VERSION_SCHEMA == "public"
    assert DATABASE_SESSION_OPTIONS == "-c timezone=UTC -c search_path=public"


def test_application_tables_are_owner_aware() -> None:
    for table_name in (
        "source_references",
        "immutable_source_evidence",
        "projection_checkpoints",
        "background_jobs",
        "outbox_events",
    ):
        table = Base.metadata.tables[f"nexora.{table_name}"]
        assert "owner_id" in table.c
        assert table.c.owner_id.nullable is False


def test_source_reference_requires_lineage_and_checksum_columns() -> None:
    table = Base.metadata.tables["nexora.source_references"]
    assert {
        "source_system",
        "source_entity_type",
        "source_entity_id",
        "source_schema_version",
        "source_version",
        "source_observed_at",
        "correlation_id",
        "payload_sha256",
        "recorded_at",
    }.issubset(table.c.keys())


def test_immutable_evidence_uses_postgresql_jsonb() -> None:
    table = Base.metadata.tables["nexora.immutable_source_evidence"]
    assert isinstance(table.c.payload.type, postgresql.JSONB)
    rendered = str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[no-untyped-call]
    assert "JSONB" in rendered
    assert "TIMESTAMP WITH TIME ZONE" in rendered


def test_security_sensitive_tables_are_explicit_without_live_capabilities() -> None:
    assert {"sessions", "webauthn_credentials", "service_tokens"}.issubset(
        table.name for table in Base.metadata.sorted_tables
    )
    forbidden = {"live_orders", "wallets", "exchange_credentials"}
    assert forbidden.isdisjoint(table.name for table in Base.metadata.sorted_tables)


def test_browser_sessions_persist_recent_reauthentication_evidence() -> None:
    sessions = Base.metadata.tables["nexora.sessions"]
    assert "reauthenticated_at" in sessions.c
    assert sessions.c.reauthenticated_at.nullable is False
    rendered = str(CreateTable(sessions).compile(dialect=postgresql.dialect()))  # type: ignore[no-untyped-call]
    assert "ck_sessions_reauthenticated_before_absolute_expiry" in rendered


def test_durable_tables_have_owner_idempotency_and_lease_fields() -> None:
    jobs = Base.metadata.tables["nexora.background_jobs"]
    outbox = Base.metadata.tables["nexora.outbox_events"]
    checkpoints = Base.metadata.tables["nexora.projection_checkpoints"]
    for table in (jobs, outbox):
        assert {"owner_id", "idempotency_key", "status", "attempt_count", "lease_owner", "lease_expires_at"}.issubset(
            table.c.keys()
        )
        assert isinstance(table.c.payload.type, postgresql.JSONB)
    assert {"owner_id", "consumer_name", "stream_name", "row_version"}.issubset(checkpoints.c.keys())


def test_trd_bot_sync_receipts_are_owner_scoped_and_immutable_input_shaped() -> None:
    receipts = Base.metadata.tables["nexora.trd_bot_sync_receipts"]
    assert {
        "owner_id",
        "event_id",
        "event_type",
        "payload_schema",
        "provider_version",
        "status",
        "reason_code",
        "envelope",
        "envelope_sha256",
    }.issubset(receipts.c.keys())
    assert isinstance(receipts.c.envelope.type, postgresql.JSONB)
