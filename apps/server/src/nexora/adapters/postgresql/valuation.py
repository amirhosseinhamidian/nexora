from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from nexora.valuation import (
    FxRateObservationView,
    ManualValuationView,
    PriceObservationView,
    ValuationConflict,
    ValuationEvidenceKind,
    ValuationEvidenceState,
    ValuationNotFound,
    ValuationSourceKind,
    ValuationStatusView,
    ValuationValidationError,
    aware_utc,
    canonical_decimal,
    canonical_request_sha256,
    evidence_state,
    normalize_positive_decimal,
    normalize_reference,
    normalize_sha256,
)

from .models import (
    AssetRecord,
    FxRateObservationRecord,
    HoldingProjectionRecord,
    ManualValuationRecord,
    PortfolioRecord,
    PriceObservationRecord,
)


def _price_view(record: PriceObservationRecord) -> PriceObservationView:
    return PriceObservationView(
        record.price_observation_id,
        record.asset_id,
        record.quote_asset_id,
        record.price,
        record.observed_at,
        record.valid_until,
        ValuationSourceKind(record.source_kind),
        record.source_reference,
        record.source_payload_sha256,
        record.idempotency_key,
        record.request_sha256,
        record.recorded_at,
    )


def _fx_view(record: FxRateObservationRecord) -> FxRateObservationView:
    return FxRateObservationView(
        record.fx_rate_observation_id,
        record.base_asset_id,
        record.quote_asset_id,
        record.rate,
        record.observed_at,
        record.valid_until,
        ValuationSourceKind(record.source_kind),
        record.source_reference,
        record.source_payload_sha256,
        record.idempotency_key,
        record.request_sha256,
        record.recorded_at,
    )


def _manual_view(record: ManualValuationRecord) -> ManualValuationView:
    return ManualValuationView(
        record.manual_valuation_id,
        record.portfolio_id,
        record.asset_id,
        record.quote_asset_id,
        record.unit_value,
        record.valued_at,
        record.valid_until,
        record.reason,
        record.source_reference,
        record.source_payload_sha256,
        record.idempotency_key,
        record.request_sha256,
        record.recorded_at,
    )


class ValuationEvidenceRepository:
    """Append-only owner-scoped price, FX and manual valuation evidence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_price_observation(
        self,
        *,
        owner_id: UUID,
        asset_id: UUID,
        quote_asset_id: UUID,
        price: str | Decimal,
        observed_at: datetime,
        valid_until: datetime,
        source_kind: ValuationSourceKind,
        source_reference: str,
        source_payload_sha256: str,
        idempotency_key: str,
    ) -> PriceObservationView:
        if asset_id == quote_asset_id:
            raise ValuationValidationError("price observation requires distinct assets")
        amount = normalize_positive_decimal(price)
        observed = aware_utc(observed_at)
        valid = aware_utc(valid_until)
        if valid <= observed:
            raise ValuationValidationError("price validity must follow observation time")
        reference = normalize_reference(source_reference, field="source reference")
        key = normalize_reference(idempotency_key, field="idempotency key")
        payload_sha256 = normalize_sha256(source_payload_sha256, field="source payload SHA-256")
        request_sha256 = canonical_request_sha256(
            {
                "asset_id": str(asset_id),
                "quote_asset_id": str(quote_asset_id),
                "price": canonical_decimal(amount),
                "observed_at": observed.isoformat(),
                "valid_until": valid.isoformat(),
                "source_kind": source_kind.value,
                "source_reference": reference,
                "source_payload_sha256": payload_sha256,
            }
        )
        record = PriceObservationRecord(
            price_observation_id=uuid4(),
            owner_id=owner_id,
            asset_id=asset_id,
            quote_asset_id=quote_asset_id,
            price=amount,
            observed_at=observed,
            valid_until=valid,
            source_kind=source_kind.value,
            source_reference=reference,
            source_payload_sha256=payload_sha256,
            idempotency_key=key,
            request_sha256=request_sha256,
        )
        return self._append_price(record)

    def _append_price(self, record: PriceObservationRecord) -> PriceObservationView:
        with self._session_factory.begin() as session:
            existing = session.scalar(
                select(PriceObservationRecord).where(
                    PriceObservationRecord.owner_id == record.owner_id,
                    PriceObservationRecord.idempotency_key == record.idempotency_key,
                )
            )
            if existing is not None:
                if existing.request_sha256 != record.request_sha256:
                    raise ValuationConflict("price observation idempotency key conflicts")
                return _price_view(existing)
            self._require_assets(session, record.owner_id, record.asset_id, record.quote_asset_id)
            session.add(record)
            try:
                session.flush()
            except IntegrityError as error:
                raise ValuationConflict("price observation conflicts with immutable evidence") from error
            return _price_view(record)

    def create_fx_rate_observation(
        self,
        *,
        owner_id: UUID,
        base_asset_id: UUID,
        quote_asset_id: UUID,
        rate: str | Decimal,
        observed_at: datetime,
        valid_until: datetime,
        source_kind: ValuationSourceKind,
        source_reference: str,
        source_payload_sha256: str,
        idempotency_key: str,
    ) -> FxRateObservationView:
        if base_asset_id == quote_asset_id:
            raise ValuationValidationError("FX observation requires distinct assets")
        amount = normalize_positive_decimal(rate)
        observed = aware_utc(observed_at)
        valid = aware_utc(valid_until)
        if valid <= observed:
            raise ValuationValidationError("FX validity must follow observation time")
        reference = normalize_reference(source_reference, field="source reference")
        key = normalize_reference(idempotency_key, field="idempotency key")
        payload_sha256 = normalize_sha256(source_payload_sha256, field="source payload SHA-256")
        request_sha256 = canonical_request_sha256(
            {
                "base_asset_id": str(base_asset_id),
                "quote_asset_id": str(quote_asset_id),
                "rate": canonical_decimal(amount),
                "observed_at": observed.isoformat(),
                "valid_until": valid.isoformat(),
                "source_kind": source_kind.value,
                "source_reference": reference,
                "source_payload_sha256": payload_sha256,
            }
        )
        record = FxRateObservationRecord(
            fx_rate_observation_id=uuid4(),
            owner_id=owner_id,
            base_asset_id=base_asset_id,
            quote_asset_id=quote_asset_id,
            rate=amount,
            observed_at=observed,
            valid_until=valid,
            source_kind=source_kind.value,
            source_reference=reference,
            source_payload_sha256=payload_sha256,
            idempotency_key=key,
            request_sha256=request_sha256,
        )
        with self._session_factory.begin() as session:
            existing = session.scalar(
                select(FxRateObservationRecord).where(
                    FxRateObservationRecord.owner_id == owner_id,
                    FxRateObservationRecord.idempotency_key == key,
                )
            )
            if existing is not None:
                if existing.request_sha256 != request_sha256:
                    raise ValuationConflict("FX observation idempotency key conflicts")
                return _fx_view(existing)
            self._require_fiat_assets(session, owner_id, base_asset_id, quote_asset_id)
            session.add(record)
            try:
                session.flush()
            except IntegrityError as error:
                raise ValuationConflict("FX observation conflicts with immutable evidence") from error
            return _fx_view(record)

    def create_manual_valuation(
        self,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        asset_id: UUID,
        quote_asset_id: UUID,
        unit_value: str | Decimal,
        valued_at: datetime,
        valid_until: datetime,
        reason: str,
        source_reference: str,
        source_payload_sha256: str,
        idempotency_key: str,
    ) -> ManualValuationView:
        if asset_id == quote_asset_id:
            raise ValuationValidationError("manual valuation requires distinct assets")
        amount = normalize_positive_decimal(unit_value)
        valued = aware_utc(valued_at)
        valid = aware_utc(valid_until)
        if valid <= valued:
            raise ValuationValidationError("manual valuation validity must follow valuation time")
        normalized_reason = normalize_reference(reason, field="manual valuation reason", minimum=8, maximum=500)
        reference = normalize_reference(source_reference, field="source reference")
        key = normalize_reference(idempotency_key, field="idempotency key")
        payload_sha256 = normalize_sha256(source_payload_sha256, field="source payload SHA-256")
        request_sha256 = canonical_request_sha256(
            {
                "portfolio_id": str(portfolio_id),
                "asset_id": str(asset_id),
                "quote_asset_id": str(quote_asset_id),
                "unit_value": canonical_decimal(amount),
                "valued_at": valued.isoformat(),
                "valid_until": valid.isoformat(),
                "reason": normalized_reason,
                "source_reference": reference,
                "source_payload_sha256": payload_sha256,
            }
        )
        record = ManualValuationRecord(
            manual_valuation_id=uuid4(),
            owner_id=owner_id,
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            quote_asset_id=quote_asset_id,
            unit_value=amount,
            valued_at=valued,
            valid_until=valid,
            reason=normalized_reason,
            source_reference=reference,
            source_payload_sha256=payload_sha256,
            idempotency_key=key,
            request_sha256=request_sha256,
        )
        with self._session_factory.begin() as session:
            existing = session.scalar(
                select(ManualValuationRecord).where(
                    ManualValuationRecord.owner_id == owner_id,
                    ManualValuationRecord.idempotency_key == key,
                )
            )
            if existing is not None:
                if existing.request_sha256 != request_sha256:
                    raise ValuationConflict("manual valuation idempotency key conflicts")
                return _manual_view(existing)
            portfolio = session.scalar(
                select(PortfolioRecord).where(
                    PortfolioRecord.owner_id == owner_id,
                    PortfolioRecord.portfolio_id == portfolio_id,
                )
            )
            if portfolio is None:
                raise ValuationNotFound("portfolio is unavailable")
            if portfolio.base_asset_id != quote_asset_id:
                raise ValuationValidationError("manual valuation quote must match the portfolio base asset")
            self._require_assets(session, owner_id, asset_id, quote_asset_id)
            session.add(record)
            try:
                session.flush()
            except IntegrityError as error:
                raise ValuationConflict("manual valuation conflicts with immutable evidence") from error
            return _manual_view(record)

    def list_price_observations(
        self, *, owner_id: UUID, asset_id: UUID | None = None, quote_asset_id: UUID | None = None, limit: int = 100
    ) -> tuple[PriceObservationView, ...]:
        statement = select(PriceObservationRecord).where(PriceObservationRecord.owner_id == owner_id)
        if asset_id is not None:
            statement = statement.where(PriceObservationRecord.asset_id == asset_id)
        if quote_asset_id is not None:
            statement = statement.where(PriceObservationRecord.quote_asset_id == quote_asset_id)
        with self._session_factory() as session:
            records = session.scalars(
                statement.order_by(
                    PriceObservationRecord.observed_at.desc(), PriceObservationRecord.price_observation_id
                ).limit(self._bounded_limit(limit))
            ).all()
            return tuple(_price_view(record) for record in records)

    def list_fx_rate_observations(
        self,
        *,
        owner_id: UUID,
        base_asset_id: UUID | None = None,
        quote_asset_id: UUID | None = None,
        limit: int = 100,
    ) -> tuple[FxRateObservationView, ...]:
        statement = select(FxRateObservationRecord).where(FxRateObservationRecord.owner_id == owner_id)
        if base_asset_id is not None:
            statement = statement.where(FxRateObservationRecord.base_asset_id == base_asset_id)
        if quote_asset_id is not None:
            statement = statement.where(FxRateObservationRecord.quote_asset_id == quote_asset_id)
        with self._session_factory() as session:
            records = session.scalars(
                statement.order_by(
                    FxRateObservationRecord.observed_at.desc(), FxRateObservationRecord.fx_rate_observation_id
                ).limit(self._bounded_limit(limit))
            ).all()
            return tuple(_fx_view(record) for record in records)

    def list_manual_valuations(
        self, *, owner_id: UUID, portfolio_id: UUID | None = None, limit: int = 100
    ) -> tuple[ManualValuationView, ...]:
        statement = select(ManualValuationRecord).where(ManualValuationRecord.owner_id == owner_id)
        if portfolio_id is not None:
            statement = statement.where(ManualValuationRecord.portfolio_id == portfolio_id)
        with self._session_factory() as session:
            records = session.scalars(
                statement.order_by(
                    ManualValuationRecord.valued_at.desc(), ManualValuationRecord.manual_valuation_id
                ).limit(self._bounded_limit(limit))
            ).all()
            return tuple(_manual_view(record) for record in records)

    def portfolio_status(
        self, *, owner_id: UUID, portfolio_id: UUID, as_of: datetime
    ) -> tuple[UUID, tuple[ValuationStatusView, ...]]:
        resolved_as_of = aware_utc(as_of)
        with self._session_factory() as session:
            portfolio = session.scalar(
                select(PortfolioRecord).where(
                    PortfolioRecord.owner_id == owner_id,
                    PortfolioRecord.portfolio_id == portfolio_id,
                )
            )
            if portfolio is None:
                raise ValuationNotFound("portfolio is unavailable")
            asset_ids = list(
                session.scalars(
                    select(HoldingProjectionRecord.asset_id)
                    .where(
                        HoldingProjectionRecord.owner_id == owner_id,
                        HoldingProjectionRecord.portfolio_id == portfolio_id,
                    )
                    .distinct()
                    .order_by(HoldingProjectionRecord.asset_id)
                ).all()
            )
            if portfolio.base_asset_id not in asset_ids:
                asset_ids.append(portfolio.base_asset_id)
            statuses = tuple(
                self._status_for_asset(
                    session,
                    owner_id=owner_id,
                    portfolio_id=portfolio_id,
                    asset_id=asset_id,
                    quote_asset_id=portfolio.base_asset_id,
                    as_of=resolved_as_of,
                )
                for asset_id in sorted(asset_ids, key=str)
            )
            return portfolio.base_asset_id, statuses

    @staticmethod
    def _status_for_asset(
        session: Session,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        asset_id: UUID,
        quote_asset_id: UUID,
        as_of: datetime,
    ) -> ValuationStatusView:
        if asset_id == quote_asset_id:
            return ValuationStatusView(
                asset_id,
                quote_asset_id,
                as_of,
                ValuationEvidenceState.FRESH,
                ValuationEvidenceKind.BASE_ASSET_IDENTITY,
                Decimal(1),
                None,
                as_of,
                None,
                "portfolio_base_asset_identity",
            )
        price = session.scalar(
            select(PriceObservationRecord)
            .where(
                PriceObservationRecord.owner_id == owner_id,
                PriceObservationRecord.asset_id == asset_id,
                PriceObservationRecord.quote_asset_id == quote_asset_id,
                PriceObservationRecord.observed_at <= as_of,
            )
            .order_by(PriceObservationRecord.observed_at.desc(), PriceObservationRecord.price_observation_id)
            .limit(1)
        )
        if price is not None:
            return ValuationStatusView(
                asset_id,
                quote_asset_id,
                as_of,
                evidence_state(as_of=as_of, valid_until=price.valid_until),
                ValuationEvidenceKind.PRICE_OBSERVATION,
                price.price,
                price.price_observation_id,
                price.observed_at,
                price.valid_until,
                price.source_reference,
            )
        manual = session.scalar(
            select(ManualValuationRecord)
            .where(
                ManualValuationRecord.owner_id == owner_id,
                ManualValuationRecord.portfolio_id == portfolio_id,
                ManualValuationRecord.asset_id == asset_id,
                ManualValuationRecord.quote_asset_id == quote_asset_id,
                ManualValuationRecord.valued_at <= as_of,
            )
            .order_by(ManualValuationRecord.valued_at.desc(), ManualValuationRecord.manual_valuation_id)
            .limit(1)
        )
        if manual is not None:
            return ValuationStatusView(
                asset_id,
                quote_asset_id,
                as_of,
                evidence_state(as_of=as_of, valid_until=manual.valid_until),
                ValuationEvidenceKind.MANUAL_VALUATION,
                manual.unit_value,
                manual.manual_valuation_id,
                manual.valued_at,
                manual.valid_until,
                manual.source_reference,
            )
        return ValuationStatusView(
            asset_id,
            quote_asset_id,
            as_of,
            ValuationEvidenceState.MISSING,
            ValuationEvidenceKind.NONE,
            None,
            None,
            None,
            None,
            None,
        )

    @staticmethod
    def _require_assets(session: Session, owner_id: UUID, *asset_ids: UUID) -> None:
        found = set(
            session.scalars(
                select(AssetRecord.asset_id).where(
                    AssetRecord.owner_id == owner_id,
                    AssetRecord.asset_id.in_(set(asset_ids)),
                )
            ).all()
        )
        if found != set(asset_ids):
            raise ValuationNotFound("asset is unavailable")

    @staticmethod
    def _require_fiat_assets(session: Session, owner_id: UUID, *asset_ids: UUID) -> None:
        records = session.execute(
            select(AssetRecord.asset_id, AssetRecord.asset_class).where(
                AssetRecord.owner_id == owner_id,
                AssetRecord.asset_id.in_(set(asset_ids)),
            )
        ).all()
        if {record.asset_id for record in records} != set(asset_ids):
            raise ValuationNotFound("asset is unavailable")
        if any(record.asset_class != "fiat" for record in records):
            raise ValuationValidationError("FX observations require two fiat assets")

    @staticmethod
    def _bounded_limit(limit: int) -> int:
        if not 1 <= limit <= 500:
            raise ValuationValidationError("list limit must be between 1 and 500")
        return limit
