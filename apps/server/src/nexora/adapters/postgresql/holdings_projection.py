from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from nexora.holdings_projection import (
    PROJECTION_VERSION,
    BasisStatus,
    CostBasisMethod,
    HoldingProjection,
    LotConsumption,
    LotProjection,
    NegativeHoldingRejected,
    ProjectionAsset,
    ProjectionConflict,
    ProjectionLeg,
    ProjectionNotFound,
    ProjectionSnapshot,
    ProjectionTransaction,
    journal_checksum,
    rebuild_projection,
)
from nexora.portfolio_registry import AssetClass
from nexora.transaction_journal import TransactionKind

from .models import (
    AssetRecord,
    HoldingProjectionRecord,
    HoldingsRebuildIssueRecord,
    HoldingsRebuildRecord,
    LotConsumptionRecord,
    LotProjectionRecord,
    PortfolioRecord,
    TransactionLegRecord,
    TransactionRecord,
)


@dataclass(frozen=True, slots=True)
class HoldingsProjectionView:
    holdings_rebuild_id: UUID
    owner_id: UUID
    rebuilt_at: datetime
    snapshot: ProjectionSnapshot


class HoldingsProjectionRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def rebuild(
        self,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        cost_basis_method: CostBasisMethod,
    ) -> HoldingsProjectionView:
        transactions: tuple[ProjectionTransaction, ...]
        assets: tuple[ProjectionAsset, ...]
        with self._session_factory.begin() as session:
            portfolio = session.scalar(
                select(PortfolioRecord)
                .where(PortfolioRecord.owner_id == owner_id, PortfolioRecord.portfolio_id == portfolio_id)
                .with_for_update()
            )
            if portfolio is None:
                raise ProjectionNotFound("portfolio is unavailable")
            assets = self._load_assets(session, owner_id)
            transactions = self._load_transactions(session, owner_id, portfolio_id)
            checksum = journal_checksum(transactions)
            existing = session.scalar(
                select(HoldingsRebuildRecord).where(
                    HoldingsRebuildRecord.owner_id == owner_id,
                    HoldingsRebuildRecord.portfolio_id == portfolio_id,
                    HoldingsRebuildRecord.cost_basis_method == cost_basis_method.value,
                    HoldingsRebuildRecord.projection_version == PROJECTION_VERSION,
                    HoldingsRebuildRecord.journal_sha256 == checksum,
                )
            )
            if existing is not None and existing.status == "succeeded":
                return self._load_view(session, existing)

        try:
            snapshot = rebuild_projection(
                portfolio_id=portfolio_id,
                cost_basis_method=cost_basis_method,
                assets=assets,
                transactions=transactions,
            )
        except NegativeHoldingRejected as error:
            self._record_rejection(
                owner_id=owner_id,
                portfolio_id=portfolio_id,
                cost_basis_method=cost_basis_method,
                checksum=checksum,
                transaction_count=len(transactions),
                last_transaction_id=transactions[-1].transaction_id if transactions else None,
                error=error,
            )
            raise

        with self._session_factory.begin() as session:
            portfolio = session.scalar(
                select(PortfolioRecord)
                .where(PortfolioRecord.owner_id == owner_id, PortfolioRecord.portfolio_id == portfolio_id)
                .with_for_update()
            )
            if portfolio is None:
                raise ProjectionNotFound("portfolio is unavailable")
            current_transactions = self._load_transactions(session, owner_id, portfolio_id)
            if journal_checksum(current_transactions) != snapshot.journal_sha256:
                raise ProjectionConflict("journal changed while the projection was being rebuilt")
            existing = session.scalar(
                select(HoldingsRebuildRecord).where(
                    HoldingsRebuildRecord.owner_id == owner_id,
                    HoldingsRebuildRecord.portfolio_id == portfolio_id,
                    HoldingsRebuildRecord.cost_basis_method == cost_basis_method.value,
                    HoldingsRebuildRecord.projection_version == PROJECTION_VERSION,
                    HoldingsRebuildRecord.journal_sha256 == snapshot.journal_sha256,
                )
            )
            if existing is not None:
                return self._load_view(session, existing)
            rebuilt_at = datetime.now(UTC)
            rebuild_id = uuid4()
            session.add(
                HoldingsRebuildRecord(
                    holdings_rebuild_id=rebuild_id,
                    owner_id=owner_id,
                    portfolio_id=portfolio_id,
                    cost_basis_method=cost_basis_method.value,
                    status="succeeded",
                    projection_version=PROJECTION_VERSION,
                    journal_sha256=snapshot.journal_sha256,
                    journal_transaction_count=snapshot.journal_transaction_count,
                    last_transaction_id=snapshot.last_transaction_id,
                    reason_code=None,
                    rebuilt_at=rebuilt_at,
                )
            )
            self._replace_snapshot(session, owner_id, snapshot, rebuilt_at)
            session.flush()
            return HoldingsProjectionView(rebuild_id, owner_id, rebuilt_at, snapshot)

    def get(
        self,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        cost_basis_method: CostBasisMethod,
    ) -> HoldingsProjectionView:
        with self._session_factory() as session:
            rebuild = session.scalar(
                select(HoldingsRebuildRecord)
                .where(
                    HoldingsRebuildRecord.owner_id == owner_id,
                    HoldingsRebuildRecord.portfolio_id == portfolio_id,
                    HoldingsRebuildRecord.cost_basis_method == cost_basis_method.value,
                    HoldingsRebuildRecord.status == "succeeded",
                )
                .order_by(HoldingsRebuildRecord.rebuilt_at.desc())
                .limit(1)
            )
            if rebuild is None:
                raise ProjectionNotFound("holdings projection has not been built")
            return self._load_view(session, rebuild)

    @staticmethod
    def _load_assets(session: Session, owner_id: UUID) -> tuple[ProjectionAsset, ...]:
        records = session.scalars(select(AssetRecord).where(AssetRecord.owner_id == owner_id)).all()
        return tuple(
            ProjectionAsset(record.asset_id, AssetClass(record.asset_class), record.precision) for record in records
        )

    @staticmethod
    def _load_transactions(session: Session, owner_id: UUID, portfolio_id: UUID) -> tuple[ProjectionTransaction, ...]:
        records = session.scalars(
            select(TransactionRecord)
            .where(TransactionRecord.owner_id == owner_id, TransactionRecord.portfolio_id == portfolio_id)
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
        by_transaction: dict[UUID, list[ProjectionLeg]] = {transaction_id: [] for transaction_id in transaction_ids}
        for leg in legs:
            by_transaction[leg.transaction_id].append(
                ProjectionLeg(
                    leg.transaction_leg_id,
                    leg.sequence,
                    leg.account_id,
                    leg.asset_id,
                    leg.quantity,
                )
            )
        return tuple(
            ProjectionTransaction(
                record.transaction_id,
                TransactionKind(record.transaction_kind),
                record.occurred_at,
                record.recorded_at,
                tuple(by_transaction[record.transaction_id]),
            )
            for record in records
        )

    def _record_rejection(
        self,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        cost_basis_method: CostBasisMethod,
        checksum: str,
        transaction_count: int,
        last_transaction_id: UUID | None,
        error: NegativeHoldingRejected,
    ) -> None:
        with self._session_factory.begin() as session:
            existing = session.scalar(
                select(HoldingsRebuildRecord).where(
                    HoldingsRebuildRecord.owner_id == owner_id,
                    HoldingsRebuildRecord.portfolio_id == portfolio_id,
                    HoldingsRebuildRecord.cost_basis_method == cost_basis_method.value,
                    HoldingsRebuildRecord.projection_version == PROJECTION_VERSION,
                    HoldingsRebuildRecord.journal_sha256 == checksum,
                )
            )
            if existing is not None:
                return
            rebuild_id = uuid4()
            session.add(
                HoldingsRebuildRecord(
                    holdings_rebuild_id=rebuild_id,
                    owner_id=owner_id,
                    portfolio_id=portfolio_id,
                    cost_basis_method=cost_basis_method.value,
                    status="rejected",
                    projection_version=PROJECTION_VERSION,
                    journal_sha256=checksum,
                    journal_transaction_count=transaction_count,
                    last_transaction_id=last_transaction_id,
                    reason_code=error.reason_code,
                )
            )
            session.flush()
            session.add(
                HoldingsRebuildIssueRecord(
                    holdings_rebuild_issue_id=uuid4(),
                    holdings_rebuild_id=rebuild_id,
                    owner_id=owner_id,
                    portfolio_id=portfolio_id,
                    cost_basis_method=cost_basis_method.value,
                    transaction_id=error.transaction_id,
                    transaction_leg_id=error.transaction_leg_id,
                    account_id=error.account_id,
                    asset_id=error.asset_id,
                    requested_quantity=error.requested_quantity,
                    available_quantity=error.available_quantity,
                    reason_code=error.reason_code,
                    journal_sha256=checksum,
                )
            )

    @staticmethod
    def _identifier(kind: str, owner_id: UUID, method: CostBasisMethod, key: str) -> UUID:
        return uuid5(NAMESPACE_URL, f"nexora:{kind}:{owner_id}:{method.value}:{key}")

    def _replace_snapshot(
        self,
        session: Session,
        owner_id: UUID,
        snapshot: ProjectionSnapshot,
        rebuilt_at: datetime,
    ) -> None:
        filters = (
            HoldingProjectionRecord.owner_id == owner_id,
            HoldingProjectionRecord.portfolio_id == snapshot.portfolio_id,
            HoldingProjectionRecord.cost_basis_method == snapshot.cost_basis_method.value,
        )
        session.execute(delete(HoldingProjectionRecord).where(*filters))
        session.execute(
            delete(LotProjectionRecord).where(
                LotProjectionRecord.owner_id == owner_id,
                LotProjectionRecord.portfolio_id == snapshot.portfolio_id,
                LotProjectionRecord.cost_basis_method == snapshot.cost_basis_method.value,
            )
        )
        session.execute(
            delete(LotConsumptionRecord).where(
                LotConsumptionRecord.owner_id == owner_id,
                LotConsumptionRecord.portfolio_id == snapshot.portfolio_id,
                LotConsumptionRecord.cost_basis_method == snapshot.cost_basis_method.value,
            )
        )
        for holding in snapshot.holdings:
            key = f"{snapshot.portfolio_id}:{holding.account_id}:{holding.asset_id}"
            session.add(
                HoldingProjectionRecord(
                    holding_projection_id=self._identifier("holding", owner_id, snapshot.cost_basis_method, key),
                    owner_id=owner_id,
                    portfolio_id=snapshot.portfolio_id,
                    account_id=holding.account_id,
                    asset_id=holding.asset_id,
                    cost_basis_method=snapshot.cost_basis_method.value,
                    quantity=holding.quantity,
                    cost_basis_asset_id=holding.cost_basis_asset_id,
                    total_cost_basis=holding.total_cost_basis,
                    average_unit_cost=holding.average_unit_cost,
                    basis_status=holding.basis_status.value,
                    projection_version=PROJECTION_VERSION,
                    journal_sha256=snapshot.journal_sha256,
                    rebuilt_at=rebuilt_at,
                )
            )
        for lot in snapshot.lots:
            session.add(
                LotProjectionRecord(
                    lot_projection_id=self._identifier("lot", owner_id, snapshot.cost_basis_method, lot.lot_key),
                    owner_id=owner_id,
                    portfolio_id=snapshot.portfolio_id,
                    account_id=lot.account_id,
                    asset_id=lot.asset_id,
                    cost_basis_method=snapshot.cost_basis_method.value,
                    lot_key=lot.lot_key,
                    source_lot_key=lot.source_lot_key,
                    acquisition_transaction_id=lot.acquisition_transaction_id,
                    acquisition_leg_id=lot.acquisition_leg_id,
                    acquired_at=lot.acquired_at,
                    original_quantity=lot.original_quantity,
                    remaining_quantity=lot.remaining_quantity,
                    cost_basis_asset_id=lot.cost_basis_asset_id,
                    original_cost_basis=lot.original_cost_basis,
                    remaining_cost_basis=lot.remaining_cost_basis,
                    basis_status=lot.basis_status.value,
                    projection_version=PROJECTION_VERSION,
                    journal_sha256=snapshot.journal_sha256,
                    rebuilt_at=rebuilt_at,
                )
            )
        for consumption in snapshot.consumptions:
            session.add(
                LotConsumptionRecord(
                    lot_consumption_id=self._identifier(
                        "consumption", owner_id, snapshot.cost_basis_method, consumption.consumption_key
                    ),
                    owner_id=owner_id,
                    portfolio_id=snapshot.portfolio_id,
                    cost_basis_method=snapshot.cost_basis_method.value,
                    consumption_key=consumption.consumption_key,
                    disposal_transaction_id=consumption.disposal_transaction_id,
                    disposal_leg_id=consumption.disposal_leg_id,
                    lot_key=consumption.lot_key,
                    quantity=consumption.quantity,
                    cost_basis_asset_id=consumption.cost_basis_asset_id,
                    allocated_cost_basis=consumption.allocated_cost_basis,
                    basis_status=consumption.basis_status.value,
                    sequence=consumption.sequence,
                    projection_version=PROJECTION_VERSION,
                    journal_sha256=snapshot.journal_sha256,
                    rebuilt_at=rebuilt_at,
                )
            )

    @staticmethod
    def _load_view(session: Session, rebuild: HoldingsRebuildRecord) -> HoldingsProjectionView:
        holdings = session.scalars(
            select(HoldingProjectionRecord)
            .where(
                HoldingProjectionRecord.owner_id == rebuild.owner_id,
                HoldingProjectionRecord.portfolio_id == rebuild.portfolio_id,
                HoldingProjectionRecord.cost_basis_method == rebuild.cost_basis_method,
                HoldingProjectionRecord.journal_sha256 == rebuild.journal_sha256,
            )
            .order_by(HoldingProjectionRecord.account_id, HoldingProjectionRecord.asset_id)
        ).all()
        lots = session.scalars(
            select(LotProjectionRecord)
            .where(
                LotProjectionRecord.owner_id == rebuild.owner_id,
                LotProjectionRecord.portfolio_id == rebuild.portfolio_id,
                LotProjectionRecord.cost_basis_method == rebuild.cost_basis_method,
                LotProjectionRecord.journal_sha256 == rebuild.journal_sha256,
            )
            .order_by(LotProjectionRecord.acquired_at, LotProjectionRecord.lot_key)
        ).all()
        consumptions = session.scalars(
            select(LotConsumptionRecord)
            .where(
                LotConsumptionRecord.owner_id == rebuild.owner_id,
                LotConsumptionRecord.portfolio_id == rebuild.portfolio_id,
                LotConsumptionRecord.cost_basis_method == rebuild.cost_basis_method,
                LotConsumptionRecord.journal_sha256 == rebuild.journal_sha256,
            )
            .order_by(LotConsumptionRecord.sequence)
        ).all()
        snapshot = ProjectionSnapshot(
            portfolio_id=rebuild.portfolio_id,
            cost_basis_method=CostBasisMethod(rebuild.cost_basis_method),
            projection_version=rebuild.projection_version,
            journal_sha256=rebuild.journal_sha256,
            journal_transaction_count=rebuild.journal_transaction_count,
            last_transaction_id=rebuild.last_transaction_id,
            holdings=tuple(
                HoldingProjection(
                    item.account_id,
                    item.asset_id,
                    item.quantity,
                    item.cost_basis_asset_id,
                    item.total_cost_basis,
                    item.average_unit_cost,
                    BasisStatus(item.basis_status),
                )
                for item in holdings
            ),
            lots=tuple(
                LotProjection(
                    item.lot_key,
                    item.source_lot_key,
                    item.account_id,
                    item.asset_id,
                    item.acquisition_transaction_id,
                    item.acquisition_leg_id,
                    item.acquired_at,
                    item.original_quantity,
                    item.remaining_quantity,
                    item.cost_basis_asset_id,
                    item.original_cost_basis,
                    item.remaining_cost_basis,
                    BasisStatus(item.basis_status),
                )
                for item in lots
            ),
            consumptions=tuple(
                LotConsumption(
                    item.consumption_key,
                    item.disposal_transaction_id,
                    item.disposal_leg_id,
                    item.lot_key,
                    item.quantity,
                    item.cost_basis_asset_id,
                    item.allocated_cost_basis,
                    BasisStatus(item.basis_status),
                    item.sequence,
                )
                for item in consumptions
            ),
        )
        return HoldingsProjectionView(rebuild.holdings_rebuild_id, rebuild.owner_id, rebuild.rebuilt_at, snapshot)
