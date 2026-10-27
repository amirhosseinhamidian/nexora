from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from nexora.adapters.postgresql import (
    CheckpointAdvance,
    DurableWorkRepository,
    JobCompletion,
    SourceEvidenceWrite,
    SyncReceiptWrite,
    TrdBotSyncReceipt,
    create_database_engine,
    load_database_settings,
)
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    database_engine = create_database_engine(load_database_settings())
    yield database_engine
    database_engine.dispose()


def test_sync_receipt_evidence_checkpoint_and_job_complete_atomically(engine: Engine) -> None:
    owner_id = uuid4()
    correlation_id = uuid4()
    now = datetime.now(UTC)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        connection.execute(
            text("INSERT INTO nexora.owner_profiles (owner_id, owner_key) VALUES (:owner_id, 'primary_owner')"),
            {"owner_id": owner_id},
        )
        factory = sessionmaker(
            bind=connection,
            class_=Session,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        repository = DurableWorkRepository(factory)
        job_id = repository.enqueue_job(
            owner_id=owner_id,
            job_type="trd_bot.event_sync",
            idempotency_key=f"integration-sync-{job_id_seed(owner_id)}",
            payload={"schema_version": "fixture-v1"},
        )
        repository.claim_jobs(
            worker_id="integration-worker",
            job_types=("trd_bot.event_sync",),
            limit=1,
            lease_seconds=60,
        )
        payload = {"schema_version": "fixture-event-v1", "value": 1}
        from nexora.adapters.postgresql import canonical_payload_sha256

        checksum = canonical_payload_sha256(payload)
        repository.complete_job(
            job_id=job_id,
            worker_id="integration-worker",
            completion=JobCompletion(
                checkpoint=CheckpointAdvance(
                    consumer_name="nexora_trd_bot_sync_v1",
                    stream_name="events",
                    cursor="cursor-1",
                    last_event_id="evt_integration_00000001",
                    provider_version="0.3.1",
                    contract_version="nexora-trd-integration-v1",
                    expected_row_version=None,
                ),
                sync_receipts=(
                    SyncReceiptWrite(
                        event_id="evt_integration_00000001",
                        event_type="decision.evaluation.completed.v1",
                        payload_schema="decision-evaluation-completed-v1",
                        provider_version="0.3.1",
                        status="applied",
                        reason_code=None,
                        envelope=payload,
                        envelope_sha256=checksum,
                    ),
                ),
                source_evidence=(
                    SourceEvidenceWrite(
                        source_entity_type="decision.evaluation.completed.v1",
                        source_entity_id="evt_integration_00000001",
                        source_schema_version="trd-integration-event-envelope-v1",
                        source_version="0.3.1",
                        source_observed_at=now,
                        correlation_id=correlation_id,
                        payload=payload,
                        payload_sha256=checksum,
                    ),
                ),
            ),
        )
        with factory() as session:
            receipt_count = session.scalar(
                select(func.count()).select_from(TrdBotSyncReceipt).where(TrdBotSyncReceipt.owner_id == owner_id)
            )
            assert receipt_count == 1
            status = session.execute(
                text("SELECT status FROM nexora.background_jobs WHERE job_id = :job_id"), {"job_id": job_id}
            ).scalar_one()
            assert status == "succeeded"
            evidence_count = session.execute(
                text("SELECT count(*) FROM nexora.immutable_source_evidence WHERE owner_id = :owner_id"),
                {"owner_id": owner_id},
            ).scalar_one()
            assert evidence_count == 1
    finally:
        transaction.rollback()
        connection.close()


def job_id_seed(owner_id: object) -> str:
    return str(owner_id).replace("-", "")[:24]
