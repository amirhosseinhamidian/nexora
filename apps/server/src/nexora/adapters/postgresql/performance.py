from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal, localcontext
from itertools import pairwise
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from nexora.holdings_projection import (
    BasisStatus,
    CostBasisMethod,
    LotConsumption,
    ProjectionAsset,
    ProjectionLeg,
    ProjectionSnapshot,
    ProjectionTransaction,
    rebuild_projection,
)
from nexora.performance import (
    PERFORMANCE_POLICY_VERSION,
    AnalyticsNotFound,
    AnalyticsState,
    ExternalFlow,
    PerformanceSeries,
    PortfolioAnalyticsSnapshot,
    PositionValue,
    RealizedPnlEvent,
    ResolvedValuation,
    analytics_state,
    bounded_series_times,
    calculate_performance_points,
    combine_analytics_states,
)
from nexora.portfolio_registry import AssetClass
from nexora.transaction_journal import TransactionKind
from nexora.valuation import ValuationEvidenceKind, ValuationEvidenceState, aware_utc, evidence_state

from .models import (
    AssetRecord,
    FxRateObservationRecord,
    ManualValuationRecord,
    PortfolioRecord,
    PriceObservationRecord,
    TransactionLegRecord,
    TransactionRecord,
)


class PortfolioPerformanceRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def snapshot(
        self,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        as_of: datetime,
        cost_basis_method: CostBasisMethod,
    ) -> PortfolioAnalyticsSnapshot:
        resolved_as_of = aware_utc(as_of)
        with self._session_factory() as session:
            return self._snapshot(
                session,
                owner_id=owner_id,
                portfolio_id=portfolio_id,
                as_of=resolved_as_of,
                cost_basis_method=cost_basis_method,
            )

    def performance_series(
        self,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        start_at: datetime,
        end_at: datetime,
        point_count: int,
        cost_basis_method: CostBasisMethod,
    ) -> PerformanceSeries:
        times = bounded_series_times(start_at, end_at, point_count)
        with self._session_factory() as session:
            portfolio = self._portfolio(session, owner_id, portfolio_id)
            snapshots = tuple(
                self._snapshot(
                    session,
                    owner_id=owner_id,
                    portfolio_id=portfolio_id,
                    as_of=as_of,
                    cost_basis_method=cost_basis_method,
                    portfolio=portfolio,
                )
                for as_of in times
            )
            flows = tuple(
                self._external_flows(
                    session,
                    owner_id=owner_id,
                    portfolio_id=portfolio_id,
                    base_asset_id=portfolio.base_asset_id,
                    start_at=start,
                    end_at=end,
                )
                for start, end in pairwise(times)
            )
        return PerformanceSeries(
            portfolio_id,
            portfolio.base_asset_id,
            cost_basis_method,
            PERFORMANCE_POLICY_VERSION,
            times[0],
            times[-1],
            calculate_performance_points(snapshots, flows),
        )

    def _snapshot(
        self,
        session: Session,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        as_of: datetime,
        cost_basis_method: CostBasisMethod,
        portfolio: PortfolioRecord | None = None,
    ) -> PortfolioAnalyticsSnapshot:
        resolved_portfolio = portfolio or self._portfolio(session, owner_id, portfolio_id)
        assets = self._assets(session, owner_id)
        transactions = self._transactions(session, owner_id, portfolio_id, as_of=as_of)
        projection = rebuild_projection(
            portfolio_id=portfolio_id,
            cost_basis_method=cost_basis_method,
            assets=tuple(assets.values()),
            transactions=transactions,
        )
        positions: list[PositionValue] = []
        calculation_states: list[AnalyticsState] = []
        for holding in projection.holdings:
            valuation = self._resolve_valuation(
                session,
                owner_id=owner_id,
                portfolio_id=portfolio_id,
                asset_id=holding.asset_id,
                quote_asset_id=resolved_portfolio.base_asset_id,
                as_of=as_of,
                assets=assets,
            )
            market_value = (
                None if valuation.unit_value is None else self._decimal_product(holding.quantity, valuation.unit_value)
            )
            basis_in_base: Decimal | None = None
            basis_state = AnalyticsState.COMPLETE
            if holding.basis_status is not BasisStatus.KNOWN or holding.total_cost_basis is None:
                basis_state = AnalyticsState.MISSING
            elif holding.cost_basis_asset_id == resolved_portfolio.base_asset_id:
                basis_in_base = holding.total_cost_basis
            elif holding.cost_basis_asset_id is not None:
                basis_valuation = self._resolve_valuation(
                    session,
                    owner_id=owner_id,
                    portfolio_id=portfolio_id,
                    asset_id=holding.cost_basis_asset_id,
                    quote_asset_id=resolved_portfolio.base_asset_id,
                    as_of=as_of,
                    assets=assets,
                )
                basis_state = analytics_state((basis_valuation.state,))
                if basis_valuation.unit_value is not None:
                    basis_in_base = self._decimal_product(holding.total_cost_basis, basis_valuation.unit_value)
            position_state = combine_analytics_states((analytics_state((valuation.state,)), basis_state))
            calculation_states.append(position_state)
            positions.append(
                PositionValue(
                    holding.account_id,
                    holding.asset_id,
                    holding.quantity,
                    valuation,
                    market_value,
                    holding.basis_status,
                    holding.cost_basis_asset_id,
                    holding.total_cost_basis,
                    basis_in_base,
                    None
                    if market_value is None or basis_in_base is None
                    else self._decimal_difference(market_value, basis_in_base),
                )
            )

        events = self._realized_events(
            session,
            owner_id=owner_id,
            portfolio_id=portfolio_id,
            base_asset_id=resolved_portfolio.base_asset_id,
            assets=assets,
            transactions=transactions,
            projection=projection,
        )
        calculation_states.extend(event.state for event in events)
        state = combine_analytics_states(tuple(calculation_states)) if calculation_states else AnalyticsState.COMPLETE
        nav_available = all(item.market_value is not None for item in positions)
        unrealized_available = all(item.unrealized_pnl is not None for item in positions)
        realized_available = all(item.realized_pnl is not None for item in events)
        return PortfolioAnalyticsSnapshot(
            portfolio_id,
            resolved_portfolio.base_asset_id,
            as_of,
            cost_basis_method,
            PERFORMANCE_POLICY_VERSION,
            projection.journal_sha256,
            projection.journal_transaction_count,
            state,
            self._decimal_sum(item.market_value or Decimal(0) for item in positions) if nav_available else None,
            self._decimal_sum(item.market_value or Decimal(0) for item in positions),
            self._decimal_sum(item.realized_pnl or Decimal(0) for item in events) if realized_available else None,
            self._decimal_sum(item.unrealized_pnl or Decimal(0) for item in positions)
            if unrealized_available
            else None,
            tuple(positions),
            events,
        )

    def _realized_events(
        self,
        session: Session,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        base_asset_id: UUID,
        assets: dict[UUID, ProjectionAsset],
        transactions: tuple[ProjectionTransaction, ...],
        projection: ProjectionSnapshot,
    ) -> tuple[RealizedPnlEvent, ...]:
        by_id = {item.transaction_id: item for item in transactions}
        consumptions_by_transaction: dict[UUID, list[LotConsumption]] = defaultdict(list)
        for consumption in projection.consumptions:
            consumptions_by_transaction[consumption.disposal_transaction_id].append(consumption)
        result: list[RealizedPnlEvent] = []
        for transaction_id in sorted(
            consumptions_by_transaction, key=lambda value: (by_id[value].occurred_at, str(value))
        ):
            transaction = by_id[transaction_id]
            if transaction.transaction_kind is not TransactionKind.SELL:
                continue
            proceeds = self._decimal_sum(
                leg.quantity
                for leg in transaction.legs
                if leg.account_id is not None and leg.asset_id == base_asset_id and leg.quantity > 0
            )
            costs: list[Decimal] = []
            states: list[AnalyticsState] = []
            reason: str | None = None
            for consumption in consumptions_by_transaction[transaction_id]:
                if consumption.basis_status is not BasisStatus.KNOWN or consumption.allocated_cost_basis is None:
                    states.append(AnalyticsState.MISSING)
                    reason = "MISSING_COST_BASIS"
                    continue
                if consumption.cost_basis_asset_id == base_asset_id:
                    costs.append(consumption.allocated_cost_basis)
                    states.append(AnalyticsState.COMPLETE)
                    continue
                if consumption.cost_basis_asset_id is None:
                    states.append(AnalyticsState.MISSING)
                    reason = "MISSING_COST_BASIS"
                    continue
                valuation = self._resolve_valuation(
                    session,
                    owner_id=owner_id,
                    portfolio_id=portfolio_id,
                    asset_id=consumption.cost_basis_asset_id,
                    quote_asset_id=base_asset_id,
                    as_of=transaction.occurred_at,
                    assets=assets,
                )
                states.append(analytics_state((valuation.state,)))
                if valuation.unit_value is None:
                    reason = "MISSING_BASIS_FX"
                else:
                    costs.append(self._decimal_product(consumption.allocated_cost_basis, valuation.unit_value))
            if proceeds <= 0:
                states.append(AnalyticsState.MISSING)
                reason = "MISSING_BASE_PROCEEDS"
            state = combine_analytics_states(tuple(states)) if states else AnalyticsState.MISSING
            cost = self._decimal_sum(costs) if state is not AnalyticsState.MISSING else None
            result.append(
                RealizedPnlEvent(
                    transaction_id,
                    transaction.occurred_at,
                    proceeds if proceeds > 0 else None,
                    cost,
                    self._decimal_difference(proceeds, cost) if proceeds > 0 and cost is not None else None,
                    state,
                    reason,
                )
            )
        return tuple(result)

    def _external_flows(
        self,
        session: Session,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        base_asset_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[ExternalFlow, ...]:
        transactions = tuple(
            item
            for item in self._transactions(session, owner_id, portfolio_id, as_of=end_at)
            if start_at < item.occurred_at <= end_at
            and item.transaction_kind
            in {TransactionKind.OPENING_BALANCE, TransactionKind.DEPOSIT, TransactionKind.WITHDRAWAL}
        )
        assets = self._assets(session, owner_id)
        result: list[ExternalFlow] = []
        for transaction in transactions:
            amounts: list[Decimal] = []
            states: list[AnalyticsState] = []
            for leg in transaction.legs:
                if leg.account_id is None:
                    continue
                valuation = self._resolve_valuation(
                    session,
                    owner_id=owner_id,
                    portfolio_id=portfolio_id,
                    asset_id=leg.asset_id,
                    quote_asset_id=base_asset_id,
                    as_of=transaction.occurred_at,
                    assets=assets,
                )
                states.append(analytics_state((valuation.state,)))
                if valuation.unit_value is not None:
                    amounts.append(self._decimal_product(leg.quantity, valuation.unit_value))
            state = combine_analytics_states(tuple(states)) if states else AnalyticsState.MISSING
            result.append(
                ExternalFlow(
                    transaction.transaction_id,
                    transaction.occurred_at,
                    self._decimal_sum(amounts) if state is not AnalyticsState.MISSING else None,
                    state,
                    "MISSING_EXTERNAL_FLOW_VALUATION" if state is AnalyticsState.MISSING else None,
                )
            )
        return tuple(result)

    @staticmethod
    def _portfolio(session: Session, owner_id: UUID, portfolio_id: UUID) -> PortfolioRecord:
        portfolio = session.scalar(
            select(PortfolioRecord).where(
                PortfolioRecord.owner_id == owner_id,
                PortfolioRecord.portfolio_id == portfolio_id,
            )
        )
        if portfolio is None:
            raise AnalyticsNotFound("portfolio is unavailable")
        return portfolio

    @staticmethod
    def _assets(session: Session, owner_id: UUID) -> dict[UUID, ProjectionAsset]:
        records = session.scalars(select(AssetRecord).where(AssetRecord.owner_id == owner_id)).all()
        return {
            record.asset_id: ProjectionAsset(record.asset_id, AssetClass(record.asset_class), record.precision)
            for record in records
        }

    @staticmethod
    def _transactions(
        session: Session, owner_id: UUID, portfolio_id: UUID, *, as_of: datetime
    ) -> tuple[ProjectionTransaction, ...]:
        records = session.scalars(
            select(TransactionRecord)
            .where(
                TransactionRecord.owner_id == owner_id,
                TransactionRecord.portfolio_id == portfolio_id,
                TransactionRecord.occurred_at <= as_of,
            )
            .order_by(TransactionRecord.occurred_at, TransactionRecord.recorded_at, TransactionRecord.transaction_id)
        ).all()
        if not records:
            return ()
        transaction_ids = [record.transaction_id for record in records]
        legs = session.scalars(
            select(TransactionLegRecord)
            .where(
                TransactionLegRecord.owner_id == owner_id,
                TransactionLegRecord.transaction_id.in_(transaction_ids),
            )
            .order_by(TransactionLegRecord.transaction_id, TransactionLegRecord.sequence)
        ).all()
        grouped: dict[UUID, list[ProjectionLeg]] = {transaction_id: [] for transaction_id in transaction_ids}
        for leg in legs:
            grouped[leg.transaction_id].append(
                ProjectionLeg(leg.transaction_leg_id, leg.sequence, leg.account_id, leg.asset_id, leg.quantity)
            )
        return tuple(
            ProjectionTransaction(
                record.transaction_id,
                TransactionKind(record.transaction_kind),
                record.occurred_at,
                record.recorded_at,
                tuple(grouped[record.transaction_id]),
            )
            for record in records
        )

    def _resolve_valuation(
        self,
        session: Session,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        asset_id: UUID,
        quote_asset_id: UUID,
        as_of: datetime,
        assets: dict[UUID, ProjectionAsset],
    ) -> ResolvedValuation:
        if asset_id == quote_asset_id:
            return ResolvedValuation(
                asset_id,
                quote_asset_id,
                as_of,
                ValuationEvidenceState.FRESH,
                ValuationEvidenceKind.BASE_ASSET_IDENTITY,
                Decimal(1),
                (),
                as_of,
                None,
                ("portfolio_base_asset_identity",),
            )
        direct_price = session.scalar(
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
        if direct_price is not None:
            return self._from_price(direct_price, quote_asset_id, as_of)

        if asset_id in assets and assets[asset_id].asset_class is AssetClass.FIAT:
            direct_fx = self._latest_fx(session, owner_id, asset_id, quote_asset_id, as_of)
            if direct_fx is not None:
                return self._from_fx(direct_fx, asset_id, quote_asset_id, as_of)

        prices = session.scalars(
            select(PriceObservationRecord)
            .where(
                PriceObservationRecord.owner_id == owner_id,
                PriceObservationRecord.asset_id == asset_id,
                PriceObservationRecord.quote_asset_id != quote_asset_id,
                PriceObservationRecord.observed_at <= as_of,
            )
            .order_by(PriceObservationRecord.observed_at.desc(), PriceObservationRecord.price_observation_id)
        ).all()
        seen_quotes: set[UUID] = set()
        for price in prices:
            if price.quote_asset_id in seen_quotes:
                continue
            seen_quotes.add(price.quote_asset_id)
            fx = self._latest_fx(session, owner_id, price.quote_asset_id, quote_asset_id, as_of)
            if fx is None:
                continue
            state = (
                ValuationEvidenceState.STALE
                if ValuationEvidenceState.STALE
                in {
                    evidence_state(as_of=as_of, valid_until=price.valid_until),
                    evidence_state(as_of=as_of, valid_until=fx.valid_until),
                }
                else ValuationEvidenceState.FRESH
            )
            with localcontext() as context:
                context.prec = 200
                unit_value = price.price * fx.rate
            return ResolvedValuation(
                asset_id,
                quote_asset_id,
                as_of,
                state,
                ValuationEvidenceKind.PRICE_OBSERVATION,
                unit_value,
                (price.price_observation_id, fx.fx_rate_observation_id),
                max(price.observed_at, fx.observed_at),
                min(price.valid_until, fx.valid_until),
                (price.source_reference, fx.source_reference),
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
            return ResolvedValuation(
                asset_id,
                quote_asset_id,
                as_of,
                evidence_state(as_of=as_of, valid_until=manual.valid_until),
                ValuationEvidenceKind.MANUAL_VALUATION,
                manual.unit_value,
                (manual.manual_valuation_id,),
                manual.valued_at,
                manual.valid_until,
                (manual.source_reference,),
            )
        return ResolvedValuation(
            asset_id,
            quote_asset_id,
            as_of,
            ValuationEvidenceState.MISSING,
            ValuationEvidenceKind.NONE,
            None,
            (),
            None,
            None,
            (),
        )

    @staticmethod
    def _decimal_product(left: Decimal, right: Decimal) -> Decimal:
        with localcontext() as context:
            context.prec = 200
            return left * right

    @staticmethod
    def _decimal_difference(left: Decimal, right: Decimal) -> Decimal:
        with localcontext() as context:
            context.prec = 200
            return left - right

    @staticmethod
    def _decimal_sum(values: Iterable[Decimal]) -> Decimal:
        with localcontext() as context:
            context.prec = 200
            return sum(values, Decimal(0))

    @staticmethod
    def _latest_fx(
        session: Session, owner_id: UUID, base_asset_id: UUID, quote_asset_id: UUID, as_of: datetime
    ) -> FxRateObservationRecord | None:
        return session.scalar(
            select(FxRateObservationRecord)
            .where(
                FxRateObservationRecord.owner_id == owner_id,
                FxRateObservationRecord.base_asset_id == base_asset_id,
                FxRateObservationRecord.quote_asset_id == quote_asset_id,
                FxRateObservationRecord.observed_at <= as_of,
            )
            .order_by(FxRateObservationRecord.observed_at.desc(), FxRateObservationRecord.fx_rate_observation_id)
            .limit(1)
        )

    @staticmethod
    def _from_price(record: PriceObservationRecord, quote_asset_id: UUID, as_of: datetime) -> ResolvedValuation:
        return ResolvedValuation(
            record.asset_id,
            quote_asset_id,
            as_of,
            evidence_state(as_of=as_of, valid_until=record.valid_until),
            ValuationEvidenceKind.PRICE_OBSERVATION,
            record.price,
            (record.price_observation_id,),
            record.observed_at,
            record.valid_until,
            (record.source_reference,),
        )

    @staticmethod
    def _from_fx(
        record: FxRateObservationRecord, asset_id: UUID, quote_asset_id: UUID, as_of: datetime
    ) -> ResolvedValuation:
        return ResolvedValuation(
            asset_id,
            quote_asset_id,
            as_of,
            evidence_state(as_of=as_of, valid_until=record.valid_until),
            ValuationEvidenceKind.FX_RATE_OBSERVATION,
            record.rate,
            (record.fx_rate_observation_id,),
            record.observed_at,
            record.valid_until,
            (record.source_reference,),
        )
