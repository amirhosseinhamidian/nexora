from __future__ import annotations

from nexora.adapters.postgresql import ALEMBIC_VERSION_SCHEMA, DATABASE_SESSION_OPTIONS, SCHEMA_NAME, Base
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable


def test_initial_schema_contains_only_the_persistence_spine() -> None:
    assert set(Base.metadata.tables) == {
        "nexora.immutable_source_evidence",
        "nexora.owner_profiles",
        "nexora.source_references",
    }
    assert all(table.schema == SCHEMA_NAME for table in Base.metadata.sorted_tables)


def test_database_namespace_cannot_become_the_implicit_search_path() -> None:
    assert ALEMBIC_VERSION_SCHEMA == "public"
    assert DATABASE_SESSION_OPTIONS == "-c timezone=UTC -c search_path=public"


def test_application_tables_are_owner_aware() -> None:
    for table_name in ("source_references", "immutable_source_evidence"):
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


def test_deferred_tables_are_not_created_early() -> None:
    forbidden = {
        "background_jobs",
        "outbox_events",
        "sessions",
        "webauthn_credentials",
        "service_tokens",
        "live_orders",
        "wallets",
    }
    assert forbidden.isdisjoint(table.name for table in Base.metadata.sorted_tables)
