from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from nexora.adapters.postgresql.models import (
    AccountRecord,
    AssetRecord,
    PortfolioRecord,
    TransactionLegRecord,
    TransactionRecord,
)
from nexora.portfolio_registry import RegistryStatus
from nexora.transaction_journal import (
    CorrectionKind,
    JournalConflict,
    JournalNotFound,
    JournalSourceKind,
    JournalValidationError,
    TransactionKind,
    TransactionLegInput,
    TransactionLegView,
    TransactionView,
    canonical_quantity,
    decimal_scale,
    normalize_idempotency_key,
    normalize_optional_text,
    normalize_quantity,
    normalize_sha256,
    normalize_source_reference,
    validate_balanced_legs,
)


def _canonical_request_sha256(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise JournalValidationError("occurred_at must include a UTC offset")
    return value.astimezone(UTC)


def _normalize_leg(leg: TransactionLegInput) -> TransactionLegInput:
    external = normalize_optional_text(
        leg.external_counterparty,
        field="external counterparty",
        maximum=160,
    )
    memo = normalize_optional_text(leg.memo, field="leg memo", maximum=240)
    return TransactionLegInput(
        account_id=leg.account_id,
        external_counterparty=external,
        asset_id=leg.asset_id,
        quantity=normalize_quantity(canonical_quantity(leg.quantity)),
        memo=memo,
    )


def _leg_view(record: TransactionLegRecord) -> TransactionLegView:
    return TransactionLegView(
        transaction_leg_id=record.transaction_leg_id,
        sequence=record.sequence,
        account_id=record.account_id,
        external_counterparty=record.external_counterparty,
        asset_id=record.asset_id,
        quantity=record.quantity,
        memo=record.memo,
    )


class TransactionJournalRepository:
    """Atomic, owner-scoped and append-only transaction journal persistence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def post_transaction(
        self,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        transaction_kind: TransactionKind,
        idempotency_key: str,
        occurred_at: datetime,
        source_kind: JournalSourceKind,
        source_reference: str,
        source_payload_sha256: str,
        legs: Sequence[TransactionLegInput] | None,
        memo: str | None = None,
        correction_of_transaction_id: UUID | None = None,
        correction_kind: CorrectionKind | None = None,
        correction_reason: str | None = None,
    ) -> TransactionView:
        normalized_key = normalize_idempotency_key(idempotency_key)
        normalized_occurred_at = _aware_utc(occurred_at)
        normalized_source_reference = normalize_source_reference(source_reference)
        normalized_source_sha = normalize_sha256(source_payload_sha256)
        normalized_memo = normalize_optional_text(memo, field="memo", maximum=500)
        normalized_reason = normalize_optional_text(
            correction_reason,
            field="correction reason",
            minimum=8,
            maximum=500,
        )
        if (correction_of_transaction_id is None) != (correction_kind is None):
            raise JournalValidationError("correction target and kind must be supplied together")
        if correction_kind is None and normalized_reason is not None:
            raise JournalValidationError("correction reason requires a correction target")
        if correction_kind is not None and normalized_reason is None:
            raise JournalValidationError("correction requires an owner-supplied reason")
        if correction_kind is CorrectionKind.REVERSAL and legs is not None:
            raise JournalValidationError("reversal legs are derived from the immutable target")
        if correction_kind is not CorrectionKind.REVERSAL and legs is None:
            raise JournalValidationError("transaction legs are required")

        request_sha256: str | None = None
        try:
            with self._session_factory.begin() as session:
                normalized_legs = self._resolve_legs(
                    session=session,
                    owner_id=owner_id,
                    portfolio_id=portfolio_id,
                    target_id=correction_of_transaction_id,
                    correction_kind=correction_kind,
                    supplied=legs,
                )
                validate_balanced_legs(normalized_legs)
                request_sha256 = self._request_sha256(
                    portfolio_id=portfolio_id,
                    transaction_kind=transaction_kind,
                    idempotency_key=normalized_key,
                    occurred_at=normalized_occurred_at,
                    source_kind=source_kind,
                    source_reference=normalized_source_reference,
                    source_payload_sha256=normalized_source_sha,
                    memo=normalized_memo,
                    correction_of_transaction_id=correction_of_transaction_id,
                    correction_kind=correction_kind,
                    correction_reason=normalized_reason,
                    legs=normalized_legs,
                )
                existing = session.scalar(
                    select(TransactionRecord).where(
                        TransactionRecord.owner_id == owner_id,
                        TransactionRecord.idempotency_key == normalized_key,
                    )
                )
                if existing is not None:
                    return self._require_matching_idempotent(session, existing, request_sha256)
                self._validate_registry_references(
                    session=session,
                    owner_id=owner_id,
                    portfolio_id=portfolio_id,
                    legs=normalized_legs,
                )

                transaction_id = uuid4()
                session.add(
                    TransactionRecord(
                        transaction_id=transaction_id,
                        owner_id=owner_id,
                        portfolio_id=portfolio_id,
                        transaction_kind=transaction_kind.value,
                        idempotency_key=normalized_key,
                        occurred_at=normalized_occurred_at,
                        source_kind=source_kind.value,
                        source_reference=normalized_source_reference,
                        source_payload_sha256=normalized_source_sha,
                        request_sha256=request_sha256,
                        memo=normalized_memo,
                        correction_of_transaction_id=correction_of_transaction_id,
                        correction_kind=correction_kind.value if correction_kind is not None else None,
                        correction_reason=normalized_reason,
                    )
                )
                session.flush()
                for sequence, leg in enumerate(normalized_legs, start=1):
                    session.add(
                        TransactionLegRecord(
                            transaction_leg_id=uuid4(),
                            owner_id=owner_id,
                            transaction_id=transaction_id,
                            sequence=sequence,
                            account_id=leg.account_id,
                            external_counterparty=leg.external_counterparty,
                            asset_id=leg.asset_id,
                            quantity=leg.quantity,
                            memo=leg.memo,
                        )
                    )
                session.flush()
                return self._get_view(session, owner_id, transaction_id)
        except IntegrityError as error:
            with self._session_factory() as session:
                existing = session.scalar(
                    select(TransactionRecord).where(
                        TransactionRecord.owner_id == owner_id,
                        TransactionRecord.idempotency_key == normalized_key,
                    )
                )
                if existing is not None and request_sha256 is not None and existing.request_sha256 == request_sha256:
                    return self._get_view(session, owner_id, existing.transaction_id)
            raise JournalConflict("journal idempotency or correction target already exists") from error

    def reverse_transaction(
        self,
        *,
        owner_id: UUID,
        transaction_id: UUID,
        idempotency_key: str,
        occurred_at: datetime,
        source_kind: JournalSourceKind,
        source_reference: str,
        source_payload_sha256: str,
        reason: str,
        memo: str | None = None,
    ) -> TransactionView:
        target = self.get_transaction(owner_id=owner_id, transaction_id=transaction_id)
        return self.post_transaction(
            owner_id=owner_id,
            portfolio_id=target.portfolio_id,
            transaction_kind=TransactionKind.ADJUSTMENT,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
            source_kind=source_kind,
            source_reference=source_reference,
            source_payload_sha256=source_payload_sha256,
            legs=None,
            memo=memo,
            correction_of_transaction_id=transaction_id,
            correction_kind=CorrectionKind.REVERSAL,
            correction_reason=reason,
        )

    def supersede_transaction(
        self,
        *,
        owner_id: UUID,
        transaction_id: UUID,
        transaction_kind: TransactionKind,
        idempotency_key: str,
        occurred_at: datetime,
        source_kind: JournalSourceKind,
        source_reference: str,
        source_payload_sha256: str,
        legs: Sequence[TransactionLegInput],
        reason: str,
        memo: str | None = None,
    ) -> TransactionView:
        target = self.get_transaction(owner_id=owner_id, transaction_id=transaction_id)
        return self.post_transaction(
            owner_id=owner_id,
            portfolio_id=target.portfolio_id,
            transaction_kind=transaction_kind,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
            source_kind=source_kind,
            source_reference=source_reference,
            source_payload_sha256=source_payload_sha256,
            legs=legs,
            memo=memo,
            correction_of_transaction_id=transaction_id,
            correction_kind=CorrectionKind.SUPERSESSION,
            correction_reason=reason,
        )

    def get_transaction(self, *, owner_id: UUID, transaction_id: UUID) -> TransactionView:
        with self._session_factory() as session:
            return self._get_view(session, owner_id, transaction_id)

    def list_transactions(
        self,
        *,
        owner_id: UUID,
        portfolio_id: UUID | None = None,
    ) -> tuple[TransactionView, ...]:
        statement = select(TransactionRecord).where(TransactionRecord.owner_id == owner_id)
        if portfolio_id is not None:
            statement = statement.where(TransactionRecord.portfolio_id == portfolio_id)
        with self._session_factory() as session:
            records = session.scalars(
                statement.order_by(
                    TransactionRecord.occurred_at.desc(),
                    TransactionRecord.recorded_at.desc(),
                    TransactionRecord.transaction_id,
                )
            ).all()
            return tuple(self._get_view(session, owner_id, record.transaction_id) for record in records)

    def _resolve_legs(
        self,
        *,
        session: Session,
        owner_id: UUID,
        portfolio_id: UUID,
        target_id: UUID | None,
        correction_kind: CorrectionKind | None,
        supplied: Sequence[TransactionLegInput] | None,
    ) -> tuple[TransactionLegInput, ...]:
        if target_id is not None:
            target = session.scalar(
                select(TransactionRecord).where(
                    TransactionRecord.owner_id == owner_id,
                    TransactionRecord.transaction_id == target_id,
                )
            )
            if target is None:
                raise JournalNotFound("correction target is unavailable")
            if target.portfolio_id != portfolio_id:
                raise JournalValidationError("correction target belongs to another portfolio")
            if correction_kind is CorrectionKind.REVERSAL:
                target_legs = session.scalars(
                    select(TransactionLegRecord)
                    .where(
                        TransactionLegRecord.owner_id == owner_id,
                        TransactionLegRecord.transaction_id == target_id,
                    )
                    .order_by(TransactionLegRecord.sequence)
                ).all()
                return tuple(
                    TransactionLegInput(
                        account_id=leg.account_id,
                        external_counterparty=leg.external_counterparty,
                        asset_id=leg.asset_id,
                        quantity=-leg.quantity,
                        memo="Reversal",
                    )
                    for leg in target_legs
                )
        if supplied is None:
            raise JournalValidationError("transaction legs are required")
        return tuple(_normalize_leg(leg) for leg in supplied)

    @staticmethod
    def _validate_registry_references(
        *,
        session: Session,
        owner_id: UUID,
        portfolio_id: UUID,
        legs: tuple[TransactionLegInput, ...],
    ) -> None:
        portfolio = session.scalar(
            select(PortfolioRecord).where(
                PortfolioRecord.owner_id == owner_id,
                PortfolioRecord.portfolio_id == portfolio_id,
                PortfolioRecord.status == RegistryStatus.ACTIVE.value,
            )
        )
        if portfolio is None:
            raise JournalNotFound("portfolio is unavailable or archived")

        asset_ids = {leg.asset_id for leg in legs}
        assets = {
            asset.asset_id: asset
            for asset in session.scalars(
                select(AssetRecord).where(
                    AssetRecord.owner_id == owner_id,
                    AssetRecord.asset_id.in_(asset_ids),
                )
            ).all()
        }
        if set(assets) != asset_ids:
            raise JournalNotFound("one or more assets are unavailable")
        for leg in legs:
            if decimal_scale(leg.quantity.normalize()) > assets[leg.asset_id].precision:
                raise JournalValidationError("leg quantity exceeds declared asset precision")

        account_ids = {leg.account_id for leg in legs if leg.account_id is not None}
        accounts = {
            account.account_id: account
            for account in session.scalars(
                select(AccountRecord).where(
                    AccountRecord.owner_id == owner_id,
                    AccountRecord.account_id.in_(account_ids),
                    AccountRecord.portfolio_id == portfolio_id,
                    AccountRecord.status == RegistryStatus.ACTIVE.value,
                )
            ).all()
        }
        if set(accounts) != account_ids:
            raise JournalNotFound("one or more accounts are unavailable, closed, or outside the portfolio")

    @staticmethod
    def _request_sha256(
        *,
        portfolio_id: UUID,
        transaction_kind: TransactionKind,
        idempotency_key: str,
        occurred_at: datetime,
        source_kind: JournalSourceKind,
        source_reference: str,
        source_payload_sha256: str,
        memo: str | None,
        correction_of_transaction_id: UUID | None,
        correction_kind: CorrectionKind | None,
        correction_reason: str | None,
        legs: tuple[TransactionLegInput, ...],
    ) -> str:
        return _canonical_request_sha256(
            {
                "portfolio_id": str(portfolio_id),
                "transaction_kind": transaction_kind.value,
                "idempotency_key": idempotency_key,
                "occurred_at": occurred_at.isoformat().replace("+00:00", "Z"),
                "source_kind": source_kind.value,
                "source_reference": source_reference,
                "source_payload_sha256": source_payload_sha256,
                "memo": memo,
                "correction_of_transaction_id": (
                    str(correction_of_transaction_id) if correction_of_transaction_id is not None else None
                ),
                "correction_kind": correction_kind.value if correction_kind is not None else None,
                "correction_reason": correction_reason,
                "legs": [
                    {
                        "account_id": str(leg.account_id) if leg.account_id is not None else None,
                        "external_counterparty": leg.external_counterparty,
                        "asset_id": str(leg.asset_id),
                        "quantity": canonical_quantity(leg.quantity),
                        "memo": leg.memo,
                    }
                    for leg in legs
                ],
            }
        )

    def _get_view(self, session: Session, owner_id: UUID, transaction_id: UUID) -> TransactionView:
        record = session.scalar(
            select(TransactionRecord).where(
                TransactionRecord.owner_id == owner_id,
                TransactionRecord.transaction_id == transaction_id,
            )
        )
        if record is None:
            raise JournalNotFound("transaction is unavailable")
        legs = session.scalars(
            select(TransactionLegRecord)
            .where(
                TransactionLegRecord.owner_id == owner_id,
                TransactionLegRecord.transaction_id == transaction_id,
            )
            .order_by(TransactionLegRecord.sequence)
        ).all()
        return TransactionView(
            transaction_id=record.transaction_id,
            portfolio_id=record.portfolio_id,
            transaction_kind=TransactionKind(record.transaction_kind),
            idempotency_key=record.idempotency_key,
            occurred_at=record.occurred_at,
            recorded_at=record.recorded_at,
            source_kind=JournalSourceKind(record.source_kind),
            source_reference=record.source_reference,
            source_payload_sha256=record.source_payload_sha256,
            request_sha256=record.request_sha256,
            memo=record.memo,
            correction_of_transaction_id=record.correction_of_transaction_id,
            correction_kind=CorrectionKind(record.correction_kind) if record.correction_kind is not None else None,
            correction_reason=record.correction_reason,
            legs=tuple(_leg_view(leg) for leg in legs),
        )

    def _require_matching_idempotent(
        self,
        session: Session,
        existing: TransactionRecord,
        request_sha256: str,
    ) -> TransactionView:
        if existing.request_sha256 != request_sha256:
            raise JournalConflict("idempotency key was already used with a different request")
        return self._get_view(session, existing.owner_id, existing.transaction_id)
