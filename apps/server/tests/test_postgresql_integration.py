from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from nexora.adapters.postgresql import create_database_engine, load_database_settings
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    database_engine = create_database_engine(load_database_settings())
    yield database_engine
    database_engine.dispose()


def test_postgresql_17_and_current_migration_head(engine: Engine) -> None:
    with engine.connect() as connection:
        server_version = int(connection.execute(text("SHOW server_version_num")).scalar_one())
        timezone = connection.execute(text("SHOW timezone")).scalar_one()
        search_path = connection.execute(text("SHOW search_path")).scalar_one()
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert 170000 <= server_version < 180000
    assert timezone == "UTC"
    assert search_path == "public"
    assert revision == "20261025_0001"


def test_expected_schema_and_tables_exist_without_deferred_capabilities(engine: Engine) -> None:
    inspector = inspect(engine)
    assert set(inspector.get_table_names(schema="nexora")) == {
        "immutable_source_evidence",
        "owner_profiles",
        "source_references",
    }
    forbidden = {"background_jobs", "outbox_events", "sessions", "live_orders", "wallets"}
    assert forbidden.isdisjoint(inspector.get_table_names(schema="nexora"))


def test_owner_scope_source_identity_and_database_immutability(engine: Engine) -> None:
    owner_id = uuid4()
    source_reference_id = uuid4()
    evidence_id = uuid4()
    correlation_id = uuid4()
    payload = '{"schema_version":"decision-evaluation-v1","status":"accepted"}'
    payload_sha256 = hashlib.sha256(payload.encode()).hexdigest()

    connection = engine.connect()
    transaction = connection.begin()
    try:
        connection.execute(
            text(
                """
                INSERT INTO nexora.owner_profiles (owner_id, owner_key)
                VALUES (:owner_id, 'primary_owner')
                """
            ),
            {"owner_id": owner_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO nexora.source_references (
                    source_reference_id, owner_id, source_system, source_entity_type,
                    source_entity_id, source_schema_version, source_version,
                    source_observed_at, correlation_id, payload_sha256
                ) VALUES (
                    :source_reference_id, :owner_id, 'trd_bot', 'decision_evaluation',
                    'decision-1', 'decision-evaluation-v1', '1',
                    :source_observed_at, :correlation_id, :payload_sha256
                )
                """
            ),
            {
                "source_reference_id": source_reference_id,
                "owner_id": owner_id,
                "source_observed_at": datetime.now(UTC),
                "correlation_id": correlation_id,
                "payload_sha256": payload_sha256,
            },
        )

        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError):
            connection.execute(
                text(
                    """
                    INSERT INTO nexora.immutable_source_evidence (
                        evidence_id, owner_id, source_reference_id, payload, payload_sha256
                    ) VALUES (
                        :evidence_id, :owner_id, :source_reference_id,
                        CAST(:payload AS jsonb), :payload_sha256
                    )
                    """
                ),
                {
                    "evidence_id": uuid4(),
                    "owner_id": owner_id,
                    "source_reference_id": source_reference_id,
                    "payload": payload,
                    "payload_sha256": "0" * 64,
                },
            )
        savepoint.rollback()

        connection.execute(
            text(
                """
                INSERT INTO nexora.immutable_source_evidence (
                    evidence_id, owner_id, source_reference_id, payload, payload_sha256
                ) VALUES (
                    :evidence_id, :owner_id, :source_reference_id,
                    CAST(:payload AS jsonb), :payload_sha256
                )
                """
            ),
            {
                "evidence_id": evidence_id,
                "owner_id": owner_id,
                "source_reference_id": source_reference_id,
                "payload": payload,
                "payload_sha256": payload_sha256,
            },
        )

        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="immutable Nexora source evidence"):
            connection.execute(
                text("UPDATE nexora.immutable_source_evidence SET payload = '{}' WHERE evidence_id = :id"),
                {"id": evidence_id},
            )
        savepoint.rollback()

        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="immutable Nexora source evidence"):
            connection.execute(
                text("DELETE FROM nexora.source_references WHERE source_reference_id = :id"),
                {"id": source_reference_id},
            )
        savepoint.rollback()

        stored_hash = connection.execute(
            text("SELECT payload_sha256 FROM nexora.immutable_source_evidence WHERE evidence_id = :id"),
            {"id": evidence_id},
        ).scalar_one()
        assert stored_hash == payload_sha256
    finally:
        transaction.rollback()
        connection.close()
