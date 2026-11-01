from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from nexora.adapters.postgresql import (
    AccountRecord,
    AssetIdentifierRecord,
    AssetRecord,
    BackgroundJob,
    CheckpointAdvance,
    CheckpointConflict,
    DurableWorkRepository,
    HoldingsProjectionRepository,
    HoldingsRebuildIssueRecord,
    ImportReconciliationRepository,
    JobCompletion,
    LeaseLost,
    OutboxEvent,
    OutboxMessage,
    PortfolioRecord,
    PortfolioRegistryRepository,
    ProjectionCheckpoint,
    TransactionJournalRepository,
    TransactionLegRecord,
    TransactionRecord,
    ValuationEvidenceRepository,
    create_database_engine,
    create_session_factory,
    load_database_settings,
)
from nexora.holdings_projection import BasisStatus, CostBasisMethod, NegativeHoldingRejected
from nexora.import_reconciliation import ImportConflict, ImportFormat, ImportRowStatus
from nexora.portfolio_registry import AccountKind, AssetClass, AssetIdentifierScheme, PortfolioKind, RegistryConflict
from nexora.transaction_journal import (
    CorrectionKind,
    JournalSourceKind,
    JournalValidationError,
    TransactionKind,
    TransactionLegInput,
)
from nexora.valuation import ValuationConflict, ValuationSourceKind, ValuationValidationError
from sqlalchemy import Engine, delete, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

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
    assert revision == "20261101_0010"


def test_expected_schema_and_tables_exist_without_security_sensitive_capabilities(engine: Engine) -> None:
    inspector = inspect(engine)
    assert set(inspector.get_table_names(schema="nexora")) == {
        "immutable_source_evidence",
        "owner_profiles",
        "projection_checkpoints",
        "background_jobs",
        "bootstrap_tokens",
        "outbox_events",
        "source_references",
        "recovery_codes",
        "security_audit_events",
        "service_tokens",
        "sessions",
        "webauthn_challenges",
        "webauthn_credentials",
        "trd_bot_sync_receipts",
        "assets",
        "asset_identifiers",
        "portfolios",
        "accounts",
        "transactions",
        "transaction_legs",
        "import_batches",
        "import_rows",
        "reconciliation_cases",
        "reconciliation_decisions",
        "holdings_rebuilds",
        "holding_projections",
        "lot_projections",
        "lot_consumptions",
        "holdings_rebuild_issues",
        "price_observations",
        "fx_rate_observations",
        "manual_valuations",
    }
    forbidden = {"live_orders", "wallets", "exchange_credentials"}
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


def test_durable_claim_reclaim_retry_checkpoint_and_outbox_are_atomic(engine: Engine) -> None:
    owner_id = uuid4()
    factory = create_session_factory(engine)
    repository = DurableWorkRepository(factory)
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO nexora.owner_profiles (owner_id, owner_key) VALUES (:owner_id, 'primary_owner')"),
            {"owner_id": owner_id},
        )
    try:
        payload = {"stream": "decision_evaluations", "cursor": None}
        job_id = repository.enqueue_job(
            owner_id=owner_id,
            job_type="trd_bot.sync",
            idempotency_key="sync-decision-evaluations-0001",
            payload=payload,
            max_attempts=3,
            available_at=now,
        )
        assert (
            repository.enqueue_job(
                owner_id=owner_id,
                job_type="trd_bot.sync",
                idempotency_key="sync-decision-evaluations-0001",
                payload=payload,
                max_attempts=3,
                available_at=now,
            )
            == job_id
        )

        first = repository.claim_jobs(
            worker_id="worker-a",
            job_types=("trd_bot.sync",),
            limit=1,
            lease_seconds=5,
            now=now,
        )
        assert len(first) == 1
        assert (
            repository.claim_jobs(
                worker_id="worker-b",
                job_types=("trd_bot.sync",),
                limit=1,
                lease_seconds=5,
                now=now,
            )
            == ()
        )

        reclaimed_at = now + timedelta(seconds=6)
        second = repository.claim_jobs(
            worker_id="worker-b",
            job_types=("trd_bot.sync",),
            limit=1,
            lease_seconds=30,
            now=reclaimed_at,
        )
        assert len(second) == 1
        assert second[0].attempt_count == 2
        with pytest.raises(LeaseLost):
            repository.complete_job(job_id=job_id, worker_id="worker-a", now=reclaimed_at)

        repository.complete_job(
            job_id=job_id,
            worker_id="worker-b",
            now=reclaimed_at,
            completion=JobCompletion(
                checkpoint=CheckpointAdvance(
                    consumer_name="trd_bot_sync",
                    stream_name="decision_evaluations",
                    cursor="cursor-1",
                    last_event_id="event-1",
                    provider_version="0.4.0",
                    contract_version="nexora-integration-v1",
                    expected_row_version=None,
                ),
                outbox=(
                    OutboxMessage(
                        event_type="source_evidence.recorded",
                        aggregate_type="decision_evaluation",
                        aggregate_id="decision-1",
                        idempotency_key="source-evidence-recorded-0001",
                        payload={"source_id": "decision-1"},
                    ),
                ),
            ),
        )
        with factory() as session:
            job = session.get(BackgroundJob, job_id)
            checkpoint = session.execute(select(ProjectionCheckpoint)).scalar_one()
            event = session.execute(select(OutboxEvent)).scalar_one()
            assert job is not None and job.status == "succeeded"
            assert checkpoint.cursor == "cursor-1" and checkpoint.row_version == 1
            assert event.status == "pending" and event.background_job_id == job_id

        claimed_events = repository.claim_outbox(
            publisher_id="publisher-a",
            limit=1,
            lease_seconds=30,
            now=reclaimed_at,
        )
        assert len(claimed_events) == 1
        repository.mark_outbox_published(
            outbox_event_id=claimed_events[0].outbox_event_id,
            publisher_id="publisher-a",
            now=reclaimed_at + timedelta(seconds=1),
        )

        conflicting_job_id = repository.enqueue_job(
            owner_id=owner_id,
            job_type="trd_bot.sync",
            idempotency_key="sync-decision-evaluations-0002",
            payload={"stream": "decision_evaluations", "cursor": "cursor-1"},
            available_at=reclaimed_at,
        )
        conflicting_claim = repository.claim_jobs(
            worker_id="worker-c",
            job_types=("trd_bot.sync",),
            limit=1,
            lease_seconds=30,
            now=reclaimed_at,
        )
        assert conflicting_claim[0].job_id == conflicting_job_id
        with pytest.raises(CheckpointConflict):
            repository.complete_job(
                job_id=conflicting_job_id,
                worker_id="worker-c",
                now=reclaimed_at,
                completion=JobCompletion(
                    checkpoint=CheckpointAdvance(
                        consumer_name="trd_bot_sync",
                        stream_name="decision_evaluations",
                        cursor="cursor-2",
                        last_event_id="event-2",
                        provider_version="0.4.0",
                        contract_version="nexora-integration-v1",
                        expected_row_version=99,
                    ),
                    outbox=(
                        OutboxMessage(
                            event_type="source_evidence.recorded",
                            aggregate_type="decision_evaluation",
                            aggregate_id="decision-2",
                            idempotency_key="source-evidence-recorded-0002",
                            payload={"source_id": "decision-2"},
                        ),
                    ),
                ),
            )
        with factory() as session:
            conflicting_job = session.get(BackgroundJob, conflicting_job_id)
            checkpoint = session.execute(select(ProjectionCheckpoint)).scalar_one()
            outbox_count = len(session.execute(select(OutboxEvent)).scalars().all())
            assert conflicting_job is not None and conflicting_job.status == "leased"
            assert checkpoint.cursor == "cursor-1" and checkpoint.row_version == 1
            assert outbox_count == 1
    finally:
        with factory.begin() as session:
            session.execute(delete(OutboxEvent).where(OutboxEvent.owner_id == owner_id))
            session.execute(delete(ProjectionCheckpoint).where(ProjectionCheckpoint.owner_id == owner_id))
            session.execute(delete(BackgroundJob).where(BackgroundJob.owner_id == owner_id))
            session.execute(
                text("DELETE FROM nexora.owner_profiles WHERE owner_id = :owner_id"), {"owner_id": owner_id}
            )


def test_portfolio_registry_lifecycle_is_owner_scoped_and_optimistically_locked(engine: Engine) -> None:
    owner_id = uuid4()
    factory = create_session_factory(engine)
    repository = PortfolioRegistryRepository(factory)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO nexora.owner_profiles (owner_id, owner_key) VALUES (:owner_id, 'primary_owner')"),
            {"owner_id": owner_id},
        )
    try:
        asset = repository.create_asset(
            owner_id=owner_id,
            asset_key="usd",
            symbol="USD",
            name="US Dollar",
            asset_class=AssetClass.FIAT,
            precision=2,
        )
        identifier = repository.add_asset_identifier(
            owner_id=owner_id,
            asset_id=asset.asset_id,
            scheme=AssetIdentifierScheme.ISO_4217,
            value="USD",
            is_primary=True,
        )
        portfolio = repository.create_portfolio(
            owner_id=owner_id,
            portfolio_key="personal-core",
            name="Personal Core",
            kind=PortfolioKind.PERSONAL,
            base_asset_id=asset.asset_id,
        )
        account = repository.create_account(
            owner_id=owner_id,
            portfolio_id=portfolio.portfolio_id,
            account_key="manual-cash",
            name="Manual Cash",
            kind=AccountKind.CASH,
        )

        assert identifier.asset_id == asset.asset_id
        assert repository.list_assets(owner_id=owner_id) == (asset,)
        assert repository.list_portfolios(owner_id=owner_id) == (portfolio,)
        assert repository.list_accounts(owner_id=owner_id, portfolio_id=portfolio.portfolio_id) == (account,)

        closed = repository.close_account(
            owner_id=owner_id,
            account_id=account.account_id,
            expected_row_version=1,
        )
        archived = repository.archive_portfolio(
            owner_id=owner_id,
            portfolio_id=portfolio.portfolio_id,
            expected_row_version=1,
        )
        inactive = repository.deactivate_asset(
            owner_id=owner_id,
            asset_id=asset.asset_id,
            expected_row_version=1,
        )
        assert (closed.status.value, archived.status.value, inactive.status.value) == (
            "closed",
            "archived",
            "inactive",
        )
        with pytest.raises(RegistryConflict):
            repository.archive_portfolio(
                owner_id=owner_id,
                portfolio_id=portfolio.portfolio_id,
                expected_row_version=1,
            )
    finally:
        with factory.begin() as session:
            session.execute(delete(AccountRecord).where(AccountRecord.owner_id == owner_id))
            session.execute(delete(PortfolioRecord).where(PortfolioRecord.owner_id == owner_id))
            session.execute(delete(AssetIdentifierRecord).where(AssetIdentifierRecord.owner_id == owner_id))
            session.execute(delete(AssetRecord).where(AssetRecord.owner_id == owner_id))
            session.execute(
                text("DELETE FROM nexora.owner_profiles WHERE owner_id = :owner_id"), {"owner_id": owner_id}
            )


def test_transaction_journal_is_balanced_idempotent_correctable_and_database_immutable(engine: Engine) -> None:
    owner_id = uuid4()
    connection = engine.connect()
    outer = connection.begin()
    factory = sessionmaker(bind=connection, class_=Session, expire_on_commit=False)
    registry = PortfolioRegistryRepository(factory)
    journal = TransactionJournalRepository(factory)
    try:
        connection.execute(
            text("INSERT INTO nexora.owner_profiles (owner_id, owner_key) VALUES (:owner_id, 'primary_owner')"),
            {"owner_id": owner_id},
        )
        asset = registry.create_asset(
            owner_id=owner_id,
            asset_key="usd",
            symbol="USD",
            name="US Dollar",
            asset_class=AssetClass.FIAT,
            precision=2,
        )
        portfolio = registry.create_portfolio(
            owner_id=owner_id,
            portfolio_key="personal-core",
            name="Personal Core",
            kind=PortfolioKind.PERSONAL,
            base_asset_id=asset.asset_id,
        )
        account = registry.create_account(
            owner_id=owner_id,
            portfolio_id=portfolio.portfolio_id,
            account_key="manual-cash",
            name="Manual Cash",
            kind=AccountKind.CASH,
        )
        legs = (
            TransactionLegInput(
                account_id=account.account_id,
                asset_id=asset.asset_id,
                quantity=Decimal("100.00"),
            ),
            TransactionLegInput(
                external_counterparty="Opening equity",
                asset_id=asset.asset_id,
                quantity=Decimal("-100.00"),
            ),
        )
        occurred_at = datetime.now(UTC)
        posted = journal.post_transaction(
            owner_id=owner_id,
            portfolio_id=portfolio.portfolio_id,
            transaction_kind=TransactionKind.OPENING_BALANCE,
            idempotency_key="manual-20261031-0001",
            occurred_at=occurred_at,
            source_kind=JournalSourceKind.MANUAL,
            source_reference="manual-entry-1",
            source_payload_sha256="a" * 64,
            legs=legs,
        )
        repeated = journal.post_transaction(
            owner_id=owner_id,
            portfolio_id=portfolio.portfolio_id,
            transaction_kind=TransactionKind.OPENING_BALANCE,
            idempotency_key="manual-20261031-0001",
            occurred_at=occurred_at,
            source_kind=JournalSourceKind.MANUAL,
            source_reference="manual-entry-1",
            source_payload_sha256="a" * 64,
            legs=legs,
        )
        assert repeated.transaction_id == posted.transaction_id

        with pytest.raises(JournalValidationError, match="at least two legs"):
            journal.post_transaction(
                owner_id=owner_id,
                portfolio_id=portfolio.portfolio_id,
                transaction_kind=TransactionKind.ADJUSTMENT,
                idempotency_key="manual-20261031-unbalanced",
                occurred_at=datetime.now(UTC),
                source_kind=JournalSourceKind.MANUAL,
                source_reference="manual-entry-unbalanced",
                source_payload_sha256="b" * 64,
                legs=(legs[0],),
            )

        reversed_entry = journal.reverse_transaction(
            owner_id=owner_id,
            transaction_id=posted.transaction_id,
            idempotency_key="manual-20261031-reversal",
            occurred_at=datetime.now(UTC),
            source_kind=JournalSourceKind.MANUAL,
            source_reference="manual-reversal-1",
            source_payload_sha256="c" * 64,
            reason="Correct an owner-confirmed opening balance",
        )
        assert reversed_entry.correction_kind is CorrectionKind.REVERSAL
        assert reversed_entry.correction_of_transaction_id == posted.transaction_id
        assert [leg.quantity for leg in reversed_entry.legs] == [Decimal("-100.00"), Decimal("100.00")]

        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="immutable"):
            connection.execute(
                text("UPDATE nexora.transactions SET memo = 'mutated' WHERE transaction_id = :transaction_id"),
                {"transaction_id": posted.transaction_id},
            )
        savepoint.rollback()
        assert len(journal.list_transactions(owner_id=owner_id, portfolio_id=portfolio.portfolio_id)) == 2
    finally:
        outer.rollback()
        connection.close()


def test_concurrent_transaction_posting_converges_on_one_idempotent_record(engine: Engine) -> None:
    owner_id = uuid4()
    factory = create_session_factory(engine)
    registry = PortfolioRegistryRepository(factory)
    journal = TransactionJournalRepository(factory)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO nexora.owner_profiles (owner_id, owner_key) VALUES (:owner_id, 'primary_owner')"),
            {"owner_id": owner_id},
        )
    asset = registry.create_asset(
        owner_id=owner_id,
        asset_key="usd",
        symbol="USD",
        name="US Dollar",
        asset_class=AssetClass.FIAT,
        precision=2,
    )
    portfolio = registry.create_portfolio(
        owner_id=owner_id,
        portfolio_key="concurrent-core",
        name="Concurrent Core",
        kind=PortfolioKind.PERSONAL,
        base_asset_id=asset.asset_id,
    )
    account = registry.create_account(
        owner_id=owner_id,
        portfolio_id=portfolio.portfolio_id,
        account_key="concurrent-cash",
        name="Concurrent Cash",
        kind=AccountKind.CASH,
    )
    occurred_at = datetime.now(UTC)
    legs = (
        TransactionLegInput(account_id=account.account_id, asset_id=asset.asset_id, quantity=Decimal("25.00")),
        TransactionLegInput(
            external_counterparty="Opening equity",
            asset_id=asset.asset_id,
            quantity=Decimal("-25.00"),
        ),
    )
    barrier = Barrier(2)

    def post_once() -> UUID:
        barrier.wait(timeout=10)
        return journal.post_transaction(
            owner_id=owner_id,
            portfolio_id=portfolio.portfolio_id,
            transaction_kind=TransactionKind.OPENING_BALANCE,
            idempotency_key="concurrent-20261031-0001",
            occurred_at=occurred_at,
            source_kind=JournalSourceKind.MANUAL,
            source_reference="concurrent-manual-entry",
            source_payload_sha256="d" * 64,
            legs=legs,
        ).transaction_id

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            transaction_ids = tuple(executor.map(lambda _: post_once(), range(2)))
        assert transaction_ids[0] == transaction_ids[1]
        with factory() as session:
            count = len(
                session.scalars(
                    select(TransactionRecord).where(
                        TransactionRecord.owner_id == owner_id,
                        TransactionRecord.idempotency_key == "concurrent-20261031-0001",
                    )
                ).all()
            )
        assert count == 1
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE nexora.transaction_legs DISABLE TRIGGER trg_transaction_legs_immutable")
            )
            connection.execute(text("ALTER TABLE nexora.transactions DISABLE TRIGGER trg_transactions_immutable"))
            connection.execute(delete(TransactionLegRecord).where(TransactionLegRecord.owner_id == owner_id))
            connection.execute(delete(TransactionRecord).where(TransactionRecord.owner_id == owner_id))
            connection.execute(text("ALTER TABLE nexora.transactions ENABLE TRIGGER trg_transactions_immutable"))
            connection.execute(
                text("ALTER TABLE nexora.transaction_legs ENABLE TRIGGER trg_transaction_legs_immutable")
            )
            connection.execute(delete(AccountRecord).where(AccountRecord.owner_id == owner_id))
            connection.execute(delete(PortfolioRecord).where(PortfolioRecord.owner_id == owner_id))
            connection.execute(delete(AssetRecord).where(AssetRecord.owner_id == owner_id))
            connection.execute(
                text("DELETE FROM nexora.owner_profiles WHERE owner_id = :owner_id"),
                {"owner_id": owner_id},
            )


def test_import_dry_run_is_idempotent_and_publication_is_atomic(engine: Engine) -> None:
    owner_id = uuid4()
    connection = engine.connect()
    outer = connection.begin()
    factory = sessionmaker(bind=connection, class_=Session, expire_on_commit=False)
    registry = PortfolioRegistryRepository(factory)
    imports = ImportReconciliationRepository(factory)
    try:
        connection.execute(
            text("INSERT INTO nexora.owner_profiles (owner_id, owner_key) VALUES (:owner_id, 'primary_owner')"),
            {"owner_id": owner_id},
        )
        asset = registry.create_asset(
            owner_id=owner_id,
            asset_key="import-usd",
            symbol="USD",
            name="Import US Dollar",
            asset_class=AssetClass.FIAT,
            precision=2,
        )
        portfolio = registry.create_portfolio(
            owner_id=owner_id,
            portfolio_key="import-core",
            name="Import Core",
            kind=PortfolioKind.PERSONAL,
            base_asset_id=asset.asset_id,
        )
        account = registry.create_account(
            owner_id=owner_id,
            portfolio_id=portfolio.portfolio_id,
            account_key="import-cash",
            name="Import Cash",
            kind=AccountKind.CASH,
        )
        content = json.dumps(
            {
                "schema_version": "nexora-transaction-import-v1",
                "rows": [
                    {
                        "row_id": "statement-1",
                        "portfolio_id": str(portfolio.portfolio_id),
                        "transaction_kind": "opening_balance",
                        "occurred_at": "2026-10-31T12:00:00Z",
                        "memo": "Imported opening balance",
                        "legs": [
                            {
                                "account_id": str(account.account_id),
                                "asset_id": str(asset.asset_id),
                                "quantity": "25.00",
                            },
                            {
                                "external_counterparty": "Opening equity",
                                "asset_id": str(asset.asset_id),
                                "quantity": "-25.00",
                            },
                        ],
                    }
                ],
            }
        )
        preview = imports.create_dry_run(owner_id=owner_id, source_format=ImportFormat.NEXORA_JSON, content=content)
        repeated = imports.create_dry_run(
            owner_id=owner_id,
            source_format=ImportFormat.NEXORA_JSON,
            content=content,
        )
        assert repeated.import_batch_id == preview.import_batch_id
        assert preview.rows[0].status is ImportRowStatus.READY
        reviewed = imports.review_batch(
            owner_id=owner_id,
            import_batch_id=preview.import_batch_id,
            reason="Owner reviewed the deterministic preview",
        )
        published = imports.publish_batch(owner_id=owner_id, import_batch_id=reviewed.import_batch_id)
        assert published.rows[0].status is ImportRowStatus.PUBLISHED
        assert (
            connection.execute(
                select(TransactionRecord.source_kind).where(TransactionRecord.owner_id == owner_id)
            ).scalar_one()
            == "import"
        )

        invalid = content.replace('"-25.00"', '"-24.00"')
        quarantined = imports.create_dry_run(
            owner_id=owner_id,
            source_format=ImportFormat.NEXORA_JSON,
            content=invalid,
        )
        with pytest.raises(ImportConflict):
            imports.review_batch(
                owner_id=owner_id,
                import_batch_id=quarantined.import_batch_id,
                reason="Owner cannot approve quarantined evidence",
            )
    finally:
        outer.rollback()
        connection.close()


def test_holdings_rebuild_persists_fifo_weighted_average_and_rejection_evidence(engine: Engine) -> None:
    owner_id = uuid4()
    connection = engine.connect()
    outer = connection.begin()
    factory = sessionmaker(bind=connection, class_=Session, expire_on_commit=False)
    registry = PortfolioRegistryRepository(factory)
    journal = TransactionJournalRepository(factory)
    projections = HoldingsProjectionRepository(factory)
    try:
        connection.execute(
            text("INSERT INTO nexora.owner_profiles (owner_id, owner_key) VALUES (:owner_id, 'primary_owner')"),
            {"owner_id": owner_id},
        )
        usd = registry.create_asset(
            owner_id=owner_id,
            asset_key="projection-usd",
            symbol="USD",
            name="Projection US Dollar",
            asset_class=AssetClass.FIAT,
            precision=2,
        )
        btc = registry.create_asset(
            owner_id=owner_id,
            asset_key="projection-btc",
            symbol="BTC",
            name="Projection Bitcoin",
            asset_class=AssetClass.CRYPTO,
            precision=8,
        )
        portfolio = registry.create_portfolio(
            owner_id=owner_id,
            portfolio_key="projection-core",
            name="Projection Core",
            kind=PortfolioKind.PERSONAL,
            base_asset_id=usd.asset_id,
        )
        account = registry.create_account(
            owner_id=owner_id,
            portfolio_id=portfolio.portfolio_id,
            account_key="projection-account",
            name="Projection Account",
            kind=AccountKind.EXCHANGE,
        )

        def post(
            sequence: int,
            kind: TransactionKind,
            legs: list[TransactionLegInput],
        ) -> None:
            journal.post_transaction(
                owner_id=owner_id,
                portfolio_id=portfolio.portfolio_id,
                transaction_kind=kind,
                idempotency_key=f"projection-entry-{sequence:04d}",
                occurred_at=datetime(2026, 11, 1, sequence, tzinfo=UTC),
                source_kind=JournalSourceKind.MANUAL,
                source_reference=f"projection-reference-{sequence}",
                source_payload_sha256=hashlib.sha256(str(sequence).encode()).hexdigest(),
                legs=legs,
            )

        post(
            1,
            TransactionKind.OPENING_BALANCE,
            [
                TransactionLegInput(usd.asset_id, Decimal("1000"), account_id=account.account_id),
                TransactionLegInput(usd.asset_id, Decimal("-1000"), external_counterparty="Opening equity"),
            ],
        )
        post(
            2,
            TransactionKind.BUY,
            [
                TransactionLegInput(btc.asset_id, Decimal("10"), account_id=account.account_id),
                TransactionLegInput(usd.asset_id, Decimal("-100"), account_id=account.account_id),
                TransactionLegInput(btc.asset_id, Decimal("-10"), external_counterparty="Market"),
                TransactionLegInput(usd.asset_id, Decimal("100"), external_counterparty="Market"),
            ],
        )
        post(
            3,
            TransactionKind.BUY,
            [
                TransactionLegInput(btc.asset_id, Decimal("5"), account_id=account.account_id),
                TransactionLegInput(usd.asset_id, Decimal("-75"), account_id=account.account_id),
                TransactionLegInput(btc.asset_id, Decimal("-5"), external_counterparty="Market"),
                TransactionLegInput(usd.asset_id, Decimal("75"), external_counterparty="Market"),
            ],
        )
        post(
            4,
            TransactionKind.SELL,
            [
                TransactionLegInput(btc.asset_id, Decimal("-12"), account_id=account.account_id),
                TransactionLegInput(usd.asset_id, Decimal("240"), account_id=account.account_id),
                TransactionLegInput(btc.asset_id, Decimal("12"), external_counterparty="Market"),
                TransactionLegInput(usd.asset_id, Decimal("-240"), external_counterparty="Market"),
            ],
        )

        fifo = projections.rebuild(
            owner_id=owner_id,
            portfolio_id=portfolio.portfolio_id,
            cost_basis_method=CostBasisMethod.FIFO,
        )
        repeated = projections.rebuild(
            owner_id=owner_id,
            portfolio_id=portfolio.portfolio_id,
            cost_basis_method=CostBasisMethod.FIFO,
        )
        weighted = projections.rebuild(
            owner_id=owner_id,
            portfolio_id=portfolio.portfolio_id,
            cost_basis_method=CostBasisMethod.WEIGHTED_AVERAGE,
        )
        fifo_btc = next(item for item in fifo.snapshot.holdings if item.asset_id == btc.asset_id)
        weighted_btc = next(item for item in weighted.snapshot.holdings if item.asset_id == btc.asset_id)
        assert repeated.holdings_rebuild_id == fifo.holdings_rebuild_id
        assert (fifo_btc.quantity, fifo_btc.total_cost_basis) == (Decimal("3"), Decimal("45"))
        assert (weighted_btc.quantity, weighted_btc.total_cost_basis) == (Decimal("3"), Decimal("35"))
        assert fifo_btc.basis_status is BasisStatus.KNOWN

        negative_portfolio = registry.create_portfolio(
            owner_id=owner_id,
            portfolio_key="projection-negative",
            name="Projection Negative",
            kind=PortfolioKind.PERSONAL,
            base_asset_id=usd.asset_id,
        )
        negative_account = registry.create_account(
            owner_id=owner_id,
            portfolio_id=negative_portfolio.portfolio_id,
            account_key="projection-negative-account",
            name="Projection Negative Account",
            kind=AccountKind.EXCHANGE,
        )
        journal.post_transaction(
            owner_id=owner_id,
            portfolio_id=negative_portfolio.portfolio_id,
            transaction_kind=TransactionKind.WITHDRAWAL,
            idempotency_key="projection-negative-0001",
            occurred_at=datetime(2026, 11, 1, 5, tzinfo=UTC),
            source_kind=JournalSourceKind.MANUAL,
            source_reference="projection-negative-reference",
            source_payload_sha256="f" * 64,
            legs=[
                TransactionLegInput(btc.asset_id, Decimal("-1"), account_id=negative_account.account_id),
                TransactionLegInput(btc.asset_id, Decimal("1"), external_counterparty="External wallet"),
            ],
        )
        with pytest.raises(NegativeHoldingRejected):
            projections.rebuild(
                owner_id=owner_id,
                portfolio_id=negative_portfolio.portfolio_id,
                cost_basis_method=CostBasisMethod.FIFO,
            )
        reason_code = connection.execute(
            select(HoldingsRebuildIssueRecord.reason_code).where(HoldingsRebuildIssueRecord.owner_id == owner_id)
        ).scalar_one()
        assert reason_code == "NEGATIVE_HOLDING_REJECTED"
    finally:
        outer.rollback()
        connection.close()


def test_valuation_evidence_is_idempotent_owner_scoped_and_append_only(engine: Engine) -> None:
    owner_id = uuid4()
    connection = engine.connect()
    outer = connection.begin()
    factory = sessionmaker(bind=connection, class_=Session, expire_on_commit=False)
    registry = PortfolioRegistryRepository(factory)
    valuation = ValuationEvidenceRepository(factory)
    try:
        connection.execute(
            text("INSERT INTO nexora.owner_profiles (owner_id, owner_key) VALUES (:owner_id, 'primary_owner')"),
            {"owner_id": owner_id},
        )
        usd = registry.create_asset(
            owner_id=owner_id,
            asset_key="valuation-usd",
            symbol="USD",
            name="Valuation US Dollar",
            asset_class=AssetClass.FIAT,
            precision=2,
        )
        btc = registry.create_asset(
            owner_id=owner_id,
            asset_key="valuation-btc",
            symbol="BTC",
            name="Valuation Bitcoin",
            asset_class=AssetClass.CRYPTO,
            precision=8,
        )
        eur = registry.create_asset(
            owner_id=owner_id,
            asset_key="valuation-eur",
            symbol="EUR",
            name="Valuation Euro",
            asset_class=AssetClass.FIAT,
            precision=2,
        )
        portfolio = registry.create_portfolio(
            owner_id=owner_id,
            portfolio_key="valuation-core",
            name="Valuation Core",
            kind=PortfolioKind.PERSONAL,
            base_asset_id=usd.asset_id,
        )
        observed = datetime(2026, 11, 1, 8, tzinfo=UTC)
        price = valuation.create_price_observation(
            owner_id=owner_id,
            asset_id=btc.asset_id,
            quote_asset_id=usd.asset_id,
            price="68123.4500",
            observed_at=observed,
            valid_until=observed + timedelta(minutes=5),
            source_kind=ValuationSourceKind.PROVIDER,
            source_reference="provider-price-1",
            source_payload_sha256="a" * 64,
            idempotency_key="valuation-price-0001",
        )
        repeated = valuation.create_price_observation(
            owner_id=owner_id,
            asset_id=btc.asset_id,
            quote_asset_id=usd.asset_id,
            price="68123.4500",
            observed_at=observed,
            valid_until=observed + timedelta(minutes=5),
            source_kind=ValuationSourceKind.PROVIDER,
            source_reference="provider-price-1",
            source_payload_sha256="a" * 64,
            idempotency_key="valuation-price-0001",
        )
        assert repeated.price_observation_id == price.price_observation_id
        with pytest.raises(ValuationConflict):
            valuation.create_price_observation(
                owner_id=owner_id,
                asset_id=btc.asset_id,
                quote_asset_id=usd.asset_id,
                price="68124",
                observed_at=observed,
                valid_until=observed + timedelta(minutes=5),
                source_kind=ValuationSourceKind.PROVIDER,
                source_reference="provider-price-1",
                source_payload_sha256="a" * 64,
                idempotency_key="valuation-price-0001",
            )
        rate = valuation.create_fx_rate_observation(
            owner_id=owner_id,
            base_asset_id=eur.asset_id,
            quote_asset_id=usd.asset_id,
            rate="1.08",
            observed_at=observed,
            valid_until=observed + timedelta(minutes=5),
            source_kind=ValuationSourceKind.IMPORT,
            source_reference="fx-import-1",
            source_payload_sha256="b" * 64,
            idempotency_key="valuation-fx-0001",
        )
        with pytest.raises(ValuationValidationError, match="two fiat assets"):
            valuation.create_fx_rate_observation(
                owner_id=owner_id,
                base_asset_id=btc.asset_id,
                quote_asset_id=usd.asset_id,
                rate="68123.45",
                observed_at=observed,
                valid_until=observed + timedelta(minutes=5),
                source_kind=ValuationSourceKind.PROVIDER,
                source_reference="invalid-crypto-fx",
                source_payload_sha256="d" * 64,
                idempotency_key="valuation-fx-invalid-0001",
            )
        manual = valuation.create_manual_valuation(
            owner_id=owner_id,
            portfolio_id=portfolio.portfolio_id,
            asset_id=btc.asset_id,
            quote_asset_id=usd.asset_id,
            unit_value="68000",
            valued_at=observed,
            valid_until=observed + timedelta(hours=1),
            reason="Owner reviewed illiquid market evidence",
            source_reference="owner-note-1",
            source_payload_sha256="c" * 64,
            idempotency_key="valuation-manual-0001",
        )
        with pytest.raises(ValuationValidationError, match="portfolio base asset"):
            valuation.create_manual_valuation(
                owner_id=owner_id,
                portfolio_id=portfolio.portfolio_id,
                asset_id=btc.asset_id,
                quote_asset_id=eur.asset_id,
                unit_value="63000",
                valued_at=observed,
                valid_until=observed + timedelta(hours=1),
                reason="Quote does not match portfolio base",
                source_reference="invalid-owner-note",
                source_payload_sha256="e" * 64,
                idempotency_key="valuation-manual-invalid-0001",
            )
        assert rate.rate == Decimal("1.08")
        assert manual.reason == "Owner reviewed illiquid market evidence"
        assert valuation.list_price_observations(owner_id=owner_id)[0].price == Decimal("68123.4500")

        nested = connection.begin_nested()
        with pytest.raises(DBAPIError):
            connection.execute(
                text("UPDATE nexora.price_observations SET price = 1 WHERE price_observation_id = :observation_id"),
                {"observation_id": price.price_observation_id},
            )
        nested.rollback()
    finally:
        outer.rollback()
        connection.close()
