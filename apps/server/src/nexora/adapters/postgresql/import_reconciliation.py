from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from nexora.adapters.postgresql.models import (
    AccountRecord,
    AssetRecord,
    ImportBatchRecord,
    ImportRowRecord,
    PortfolioRecord,
    ReconciliationCaseRecord,
    ReconciliationDecisionRecord,
    TransactionLegRecord,
    TransactionRecord,
)
from nexora.import_reconciliation import (
    ImportBatchStatus,
    ImportBatchView,
    ImportConflict,
    ImportFormat,
    ImportNotFound,
    ImportRowStatus,
    ImportRowView,
    ImportValidationError,
    NormalizedImportRow,
    ReconciliationCaseView,
    ReconciliationState,
    normalize_decision_reason,
    normalize_import,
    restore_normalized_row,
)
from nexora.portfolio_registry import RegistryStatus
from nexora.transaction_journal import canonical_quantity, decimal_scale


def _canonical_sha256(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _row_view(record: ImportRowRecord) -> ImportRowView:
    return ImportRowView(
        import_row_id=record.import_row_id,
        row_number=record.row_number,
        external_row_id=record.external_row_id,
        fingerprint_sha256=record.fingerprint_sha256,
        status=ImportRowStatus(record.status),
        reason_code=record.reason_code,
        normalized_payload=record.normalized_payload,
    )


def _case_view(record: ReconciliationCaseRecord) -> ReconciliationCaseView:
    return ReconciliationCaseView(
        reconciliation_case_id=record.reconciliation_case_id,
        import_batch_id=record.import_batch_id,
        import_row_id=record.import_row_id,
        transaction_id=record.transaction_id,
        state=ReconciliationState(record.state),
        difference_code=record.difference_code,
        reason=record.reason,
        row_version=record.row_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class ImportReconciliationRepository:
    """Owner-scoped dry-run import, atomic publication and review evidence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_dry_run(self, *, owner_id: UUID, source_format: ImportFormat, content: str) -> ImportBatchView:
        preview = normalize_import(source_format, content)
        try:
            with self._session_factory.begin() as session:
                existing = session.scalar(
                    select(ImportBatchRecord).where(
                        ImportBatchRecord.owner_id == owner_id,
                        ImportBatchRecord.content_sha256 == preview.content_sha256,
                    )
                )
                if existing is not None:
                    return self._batch_view(session, existing)
                batch_id = uuid4()
                row_records: list[ImportRowRecord] = []
                cases: list[ReconciliationCaseRecord] = []
                ready_count = duplicate_count = quarantined_count = 0
                for row in preview.rows:
                    row_id = uuid4()
                    if isinstance(row, NormalizedImportRow):
                        duplicate = session.scalar(
                            select(ImportRowRecord.import_row_id)
                            .where(
                                ImportRowRecord.owner_id == owner_id,
                                ImportRowRecord.fingerprint_sha256 == row.fingerprint_sha256,
                                ImportRowRecord.status.in_(["ready", "duplicate", "published"]),
                            )
                            .limit(1)
                        )
                        if duplicate is None:
                            status = ImportRowStatus.READY
                            reason_code = None
                            ready_count += 1
                        else:
                            status = ImportRowStatus.DUPLICATE
                            reason_code = "DUPLICATE_PREVIOUS_IMPORT"
                            duplicate_count += 1
                        row_record = ImportRowRecord(
                            import_row_id=row_id,
                            owner_id=owner_id,
                            import_batch_id=batch_id,
                            row_number=row.row_number,
                            external_row_id=row.external_row_id,
                            fingerprint_sha256=row.fingerprint_sha256,
                            status=status.value,
                            reason_code=reason_code,
                            normalized_payload=row.canonical_payload,
                        )
                        if status is ImportRowStatus.DUPLICATE:
                            cases.append(
                                ReconciliationCaseRecord(
                                    reconciliation_case_id=uuid4(),
                                    owner_id=owner_id,
                                    import_batch_id=batch_id,
                                    import_row_id=row_id,
                                    state=ReconciliationState.MATCHED.value,
                                    difference_code=reason_code,
                                    reason="Deterministic duplicate evidence matched",
                                )
                            )
                    else:
                        status = (
                            ImportRowStatus.DUPLICATE
                            if row.reason_code == "DUPLICATE_WITHIN_BATCH"
                            else ImportRowStatus.QUARANTINED
                        )
                        if status is ImportRowStatus.DUPLICATE:
                            duplicate_count += 1
                            state = ReconciliationState.MATCHED
                        else:
                            quarantined_count += 1
                            state = ReconciliationState.OPEN
                        row_record = ImportRowRecord(
                            import_row_id=row_id,
                            owner_id=owner_id,
                            import_batch_id=batch_id,
                            row_number=row.row_number,
                            external_row_id=row.external_row_id,
                            fingerprint_sha256=None,
                            status=status.value,
                            reason_code=row.reason_code,
                            normalized_payload=None,
                        )
                        cases.append(
                            ReconciliationCaseRecord(
                                reconciliation_case_id=uuid4(),
                                owner_id=owner_id,
                                import_batch_id=batch_id,
                                import_row_id=row_id,
                                state=state.value,
                                difference_code=row.reason_code,
                                reason=row.detail[:500] if len(row.detail) >= 8 else "Import row requires owner review",
                            )
                        )
                    row_records.append(row_record)
                batch_status = ImportBatchStatus.QUARANTINED if quarantined_count else ImportBatchStatus.DRY_RUN
                batch = ImportBatchRecord(
                    import_batch_id=batch_id,
                    owner_id=owner_id,
                    source_format=source_format.value,
                    content_sha256=preview.content_sha256,
                    status=batch_status.value,
                    row_count=len(preview.rows),
                    ready_count=ready_count,
                    duplicate_count=duplicate_count,
                    quarantined_count=quarantined_count,
                )
                session.add(batch)
                session.add_all(row_records)
                session.flush()
                session.add_all(cases)
                session.flush()
                return self._batch_view(session, batch)
        except IntegrityError as error:
            with self._session_factory() as session:
                existing = session.scalar(
                    select(ImportBatchRecord).where(
                        ImportBatchRecord.owner_id == owner_id,
                        ImportBatchRecord.content_sha256 == preview.content_sha256,
                    )
                )
                if existing is not None:
                    return self._batch_view(session, existing)
            raise ImportConflict("import content checksum changed concurrently") from error

    def review_batch(self, *, owner_id: UUID, import_batch_id: UUID, reason: str) -> ImportBatchView:
        normalized_reason = normalize_decision_reason(reason, required=True)
        with self._session_factory.begin() as session:
            batch = self._locked_batch(session, owner_id, import_batch_id)
            if batch.status == ImportBatchStatus.REVIEWED.value:
                if batch.review_reason != normalized_reason:
                    raise ImportConflict("batch was reviewed with different evidence")
                return self._batch_view(session, batch)
            if batch.status != ImportBatchStatus.DRY_RUN.value or batch.quarantined_count:
                raise ImportConflict("only a clean dry-run batch can be reviewed")
            batch.status = ImportBatchStatus.REVIEWED.value
            batch.review_reason = normalized_reason
            batch.reviewed_at = datetime.now(UTC)
            session.flush()
            return self._batch_view(session, batch)

    def publish_batch(self, *, owner_id: UUID, import_batch_id: UUID) -> ImportBatchView:
        with self._session_factory.begin() as session:
            batch = self._locked_batch(session, owner_id, import_batch_id)
            if batch.status == ImportBatchStatus.PUBLISHED.value:
                return self._batch_view(session, batch)
            if batch.status != ImportBatchStatus.REVIEWED.value or batch.quarantined_count:
                raise ImportConflict("batch must be clean and owner-reviewed before publication")
            rows = session.scalars(
                select(ImportRowRecord)
                .where(
                    ImportRowRecord.owner_id == owner_id,
                    ImportRowRecord.import_batch_id == import_batch_id,
                    ImportRowRecord.status == ImportRowStatus.READY.value,
                )
                .order_by(ImportRowRecord.row_number)
                .with_for_update()
            ).all()
            for record in rows:
                if record.normalized_payload is None or record.fingerprint_sha256 is None:
                    raise ImportConflict("ready row is missing normalized evidence")
                normalized = restore_normalized_row(record.normalized_payload, record.row_number)
                if normalized.fingerprint_sha256 != record.fingerprint_sha256:
                    raise ImportConflict("normalized row checksum drifted")
                transaction_id = self._publish_row(
                    session=session,
                    owner_id=owner_id,
                    batch=batch,
                    record=record,
                    normalized=normalized,
                )
                record.status = ImportRowStatus.PUBLISHED.value
                case = session.scalar(
                    select(ReconciliationCaseRecord).where(
                        ReconciliationCaseRecord.owner_id == owner_id,
                        ReconciliationCaseRecord.import_row_id == record.import_row_id,
                    )
                )
                if case is not None:
                    case.transaction_id = transaction_id
            batch.status = ImportBatchStatus.PUBLISHED.value
            batch.published_at = datetime.now(UTC)
            session.flush()
            return self._batch_view(session, batch)

    def get_batch(self, *, owner_id: UUID, import_batch_id: UUID) -> ImportBatchView:
        with self._session_factory() as session:
            batch = session.scalar(
                select(ImportBatchRecord).where(
                    ImportBatchRecord.owner_id == owner_id,
                    ImportBatchRecord.import_batch_id == import_batch_id,
                )
            )
            if batch is None:
                raise ImportNotFound("import batch is unavailable")
            return self._batch_view(session, batch)

    def list_batches(self, *, owner_id: UUID) -> tuple[ImportBatchView, ...]:
        with self._session_factory() as session:
            batches = session.scalars(
                select(ImportBatchRecord)
                .where(ImportBatchRecord.owner_id == owner_id)
                .order_by(ImportBatchRecord.created_at.desc(), ImportBatchRecord.import_batch_id)
            ).all()
            return tuple(self._batch_view(session, batch) for batch in batches)

    def list_reconciliation_cases(self, *, owner_id: UUID) -> tuple[ReconciliationCaseView, ...]:
        with self._session_factory() as session:
            records = session.scalars(
                select(ReconciliationCaseRecord)
                .where(ReconciliationCaseRecord.owner_id == owner_id)
                .order_by(ReconciliationCaseRecord.created_at, ReconciliationCaseRecord.reconciliation_case_id)
            ).all()
            return tuple(_case_view(record) for record in records)

    def decide_reconciliation_case(
        self,
        *,
        owner_id: UUID,
        reconciliation_case_id: UUID,
        state: ReconciliationState,
        expected_row_version: int,
        reason: str | None,
    ) -> ReconciliationCaseView:
        if state is ReconciliationState.OPEN:
            raise ImportValidationError("a reconciliation decision cannot transition back to open")
        normalized_reason = normalize_decision_reason(reason, required=True)
        with self._session_factory.begin() as session:
            record = session.scalar(
                select(ReconciliationCaseRecord).where(
                    ReconciliationCaseRecord.owner_id == owner_id,
                    ReconciliationCaseRecord.reconciliation_case_id == reconciliation_case_id,
                )
            )
            if record is None:
                raise ImportNotFound("reconciliation case is unavailable")
            previous = ReconciliationState(record.state)
            changed_version = session.scalar(
                update(ReconciliationCaseRecord)
                .where(
                    ReconciliationCaseRecord.owner_id == owner_id,
                    ReconciliationCaseRecord.reconciliation_case_id == reconciliation_case_id,
                    ReconciliationCaseRecord.row_version == expected_row_version,
                )
                .values(
                    state=state.value,
                    reason=normalized_reason,
                    row_version=ReconciliationCaseRecord.row_version + 1,
                    updated_at=datetime.now(UTC),
                )
                .returning(ReconciliationCaseRecord.row_version)
            )
            if changed_version is None:
                raise ImportConflict("reconciliation case changed concurrently")
            session.add(
                ReconciliationDecisionRecord(
                    reconciliation_decision_id=uuid4(),
                    owner_id=owner_id,
                    reconciliation_case_id=reconciliation_case_id,
                    from_state=previous.value,
                    to_state=state.value,
                    reason=normalized_reason,
                )
            )
            session.flush()
            changed = session.get(ReconciliationCaseRecord, reconciliation_case_id)
            if changed is None:
                raise ImportNotFound("reconciliation case is unavailable")
            return _case_view(changed)

    @staticmethod
    def _locked_batch(session: Session, owner_id: UUID, import_batch_id: UUID) -> ImportBatchRecord:
        batch = session.scalar(
            select(ImportBatchRecord)
            .where(
                ImportBatchRecord.owner_id == owner_id,
                ImportBatchRecord.import_batch_id == import_batch_id,
            )
            .with_for_update()
        )
        if batch is None:
            raise ImportNotFound("import batch is unavailable")
        return batch

    @staticmethod
    def _batch_view(session: Session, batch: ImportBatchRecord) -> ImportBatchView:
        rows = session.scalars(
            select(ImportRowRecord)
            .where(
                ImportRowRecord.owner_id == batch.owner_id,
                ImportRowRecord.import_batch_id == batch.import_batch_id,
            )
            .order_by(ImportRowRecord.row_number)
        ).all()
        return ImportBatchView(
            import_batch_id=batch.import_batch_id,
            source_format=ImportFormat(batch.source_format),
            content_sha256=batch.content_sha256,
            status=ImportBatchStatus(batch.status),
            row_count=batch.row_count,
            ready_count=batch.ready_count,
            duplicate_count=batch.duplicate_count,
            quarantined_count=batch.quarantined_count,
            review_reason=batch.review_reason,
            created_at=batch.created_at,
            reviewed_at=batch.reviewed_at,
            published_at=batch.published_at,
            rows=tuple(_row_view(row) for row in rows),
        )

    @staticmethod
    def _publish_row(
        *,
        session: Session,
        owner_id: UUID,
        batch: ImportBatchRecord,
        record: ImportRowRecord,
        normalized: NormalizedImportRow,
    ) -> UUID:
        portfolio = session.scalar(
            select(PortfolioRecord).where(
                PortfolioRecord.owner_id == owner_id,
                PortfolioRecord.portfolio_id == normalized.portfolio_id,
                PortfolioRecord.status == RegistryStatus.ACTIVE.value,
            )
        )
        if portfolio is None:
            raise ImportConflict("import row references an unavailable portfolio")
        assets = {
            asset.asset_id: asset
            for asset in session.scalars(
                select(AssetRecord).where(
                    AssetRecord.owner_id == owner_id,
                    AssetRecord.asset_id.in_({leg.asset_id for leg in normalized.legs}),
                    AssetRecord.status == RegistryStatus.ACTIVE.value,
                )
            ).all()
        }
        accounts = {
            account.account_id: account
            for account in session.scalars(
                select(AccountRecord).where(
                    AccountRecord.owner_id == owner_id,
                    AccountRecord.account_id.in_({leg.account_id for leg in normalized.legs if leg.account_id}),
                    AccountRecord.status == RegistryStatus.ACTIVE.value,
                )
            ).all()
        }
        for leg in normalized.legs:
            asset = assets.get(leg.asset_id)
            if asset is None or decimal_scale(leg.quantity) > asset.precision:
                raise ImportConflict("import row asset is unavailable or exceeds declared precision")
            if leg.account_id is not None:
                account = accounts.get(leg.account_id)
                if account is None or account.portfolio_id != normalized.portfolio_id:
                    raise ImportConflict("import row account is unavailable or belongs to another portfolio")
        idempotency_key = f"import-{batch.import_batch_id}-{record.row_number:06d}"
        request_payload: dict[str, object] = {
            "portfolio_id": str(normalized.portfolio_id),
            "transaction_kind": normalized.transaction_kind.value,
            "idempotency_key": idempotency_key,
            "occurred_at": normalized.occurred_at.isoformat().replace("+00:00", "Z"),
            "source_kind": "import",
            "source_reference": f"import:{batch.import_batch_id}:{record.row_number}",
            "source_payload_sha256": batch.content_sha256,
            "memo": normalized.memo,
            "correction_of_transaction_id": None,
            "correction_kind": None,
            "correction_reason": None,
            "legs": [
                {
                    "account_id": str(leg.account_id) if leg.account_id else None,
                    "external_counterparty": leg.external_counterparty,
                    "asset_id": str(leg.asset_id),
                    "quantity": canonical_quantity(leg.quantity),
                    "memo": leg.memo,
                }
                for leg in normalized.legs
            ],
        }
        transaction_id = uuid4()
        session.add(
            TransactionRecord(
                transaction_id=transaction_id,
                owner_id=owner_id,
                portfolio_id=normalized.portfolio_id,
                transaction_kind=normalized.transaction_kind.value,
                idempotency_key=idempotency_key,
                occurred_at=normalized.occurred_at,
                source_kind="import",
                source_reference=f"import:{batch.import_batch_id}:{record.row_number}",
                source_payload_sha256=batch.content_sha256,
                request_sha256=_canonical_sha256(request_payload),
                memo=normalized.memo,
            )
        )
        session.flush()
        for sequence, leg in enumerate(normalized.legs, start=1):
            session.add(
                TransactionLegRecord(
                    transaction_leg_id=uuid4(),
                    owner_id=owner_id,
                    transaction_id=transaction_id,
                    sequence=sequence,
                    account_id=leg.account_id,
                    external_counterparty=leg.external_counterparty,
                    asset_id=leg.asset_id,
                    quantity=Decimal(canonical_quantity(leg.quantity)),
                    memo=leg.memo,
                )
            )
        session.flush()
        return transaction_id
