from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from enum import StrEnum
from uuid import UUID

from nexora.portfolio_registry import AssetClass
from nexora.transaction_journal import TransactionKind, canonical_quantity

PROJECTION_VERSION = "nexora-holdings-projection-v1"


class CostBasisMethod(StrEnum):
    FIFO = "fifo"
    WEIGHTED_AVERAGE = "weighted_average"


class BasisStatus(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    MIXED = "mixed"


class ProjectionError(RuntimeError):
    """Base error for holdings projection operations."""


class ProjectionNotFound(ProjectionError):
    """The requested owner-scoped projection is unavailable."""


class ProjectionConflict(ProjectionError):
    """The requested projection transition conflicts with durable state."""


class ProjectionValidationError(ProjectionError):
    """Journal evidence cannot be projected without weakening accounting rules."""


class NegativeHoldingRejected(ProjectionValidationError):
    def __init__(
        self,
        *,
        transaction_id: UUID,
        transaction_leg_id: UUID,
        account_id: UUID,
        asset_id: UUID,
        requested_quantity: Decimal,
        available_quantity: Decimal,
    ) -> None:
        super().__init__("journal would create a negative owner-account holding")
        self.transaction_id = transaction_id
        self.transaction_leg_id = transaction_leg_id
        self.account_id = account_id
        self.asset_id = asset_id
        self.requested_quantity = requested_quantity
        self.available_quantity = available_quantity
        self.reason_code = "NEGATIVE_HOLDING_REJECTED"


@dataclass(frozen=True, slots=True)
class ProjectionAsset:
    asset_id: UUID
    asset_class: AssetClass
    precision: int


@dataclass(frozen=True, slots=True)
class ProjectionLeg:
    transaction_leg_id: UUID
    sequence: int
    account_id: UUID | None
    asset_id: UUID
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class ProjectionTransaction:
    transaction_id: UUID
    transaction_kind: TransactionKind
    occurred_at: datetime
    recorded_at: datetime
    legs: tuple[ProjectionLeg, ...]


@dataclass(frozen=True, slots=True)
class HoldingProjection:
    account_id: UUID
    asset_id: UUID
    quantity: Decimal
    cost_basis_asset_id: UUID | None
    total_cost_basis: Decimal | None
    average_unit_cost: Decimal | None
    basis_status: BasisStatus


@dataclass(frozen=True, slots=True)
class LotProjection:
    lot_key: str
    source_lot_key: str | None
    account_id: UUID
    asset_id: UUID
    acquisition_transaction_id: UUID
    acquisition_leg_id: UUID
    acquired_at: datetime
    original_quantity: Decimal
    remaining_quantity: Decimal
    cost_basis_asset_id: UUID | None
    original_cost_basis: Decimal | None
    remaining_cost_basis: Decimal | None
    basis_status: BasisStatus


@dataclass(frozen=True, slots=True)
class LotConsumption:
    consumption_key: str
    disposal_transaction_id: UUID
    disposal_leg_id: UUID
    lot_key: str
    quantity: Decimal
    cost_basis_asset_id: UUID | None
    allocated_cost_basis: Decimal | None
    basis_status: BasisStatus
    sequence: int


@dataclass(frozen=True, slots=True)
class ProjectionSnapshot:
    portfolio_id: UUID
    cost_basis_method: CostBasisMethod
    projection_version: str
    journal_sha256: str
    journal_transaction_count: int
    last_transaction_id: UUID | None
    holdings: tuple[HoldingProjection, ...]
    lots: tuple[LotProjection, ...]
    consumptions: tuple[LotConsumption, ...]


@dataclass(slots=True)
class _Lot:
    lot_key: str
    source_lot_key: str | None
    account_id: UUID
    asset_id: UUID
    acquisition_transaction_id: UUID
    acquisition_leg_id: UUID
    acquired_at: datetime
    original_quantity: Decimal
    remaining_quantity: Decimal
    cost_basis_asset_id: UUID | None
    original_cost_basis: Decimal | None
    remaining_cost_basis: Decimal | None
    basis_status: BasisStatus


@dataclass(frozen=True, slots=True)
class _Slice:
    source_lot_key: str
    acquisition_transaction_id: UUID
    acquisition_leg_id: UUID
    acquired_at: datetime
    quantity: Decimal
    cost_basis_asset_id: UUID | None
    cost_basis: Decimal | None
    basis_status: BasisStatus


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProjectionValidationError("projection timestamps must include a UTC offset")
    return value.astimezone(UTC)


def _sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _rounded(value: Decimal, precision: int) -> Decimal:
    with localcontext() as context:
        context.prec = 90
        return value.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_EVEN)


def _allocate(total: Decimal, weights: list[Decimal], precision: int) -> list[Decimal]:
    weight_total = sum(weights, Decimal(0))
    if not weights or weight_total <= 0 or any(weight < 0 for weight in weights):
        raise ProjectionValidationError("allocation requires positive deterministic weights")
    result: list[Decimal] = []
    remainder = total
    with localcontext() as context:
        context.prec = 90
        for index, weight in enumerate(weights):
            value = remainder if index == len(weights) - 1 else _rounded(total * weight / weight_total, precision)
            result.append(value)
            remainder -= value
    if sum(result, Decimal(0)) != total:
        raise ProjectionValidationError("rounded allocation does not preserve the exact total")
    return result


def _key(*parts: object) -> str:
    return _sha256([str(part) if part is not None else None for part in parts])


def journal_checksum(transactions: tuple[ProjectionTransaction, ...]) -> str:
    ordered = sorted(
        transactions,
        key=lambda item: (_aware_utc(item.occurred_at), _aware_utc(item.recorded_at), str(item.transaction_id)),
    )
    return _sha256(
        [
            {
                "transaction_id": str(transaction.transaction_id),
                "transaction_kind": transaction.transaction_kind.value,
                "occurred_at": _aware_utc(transaction.occurred_at).isoformat().replace("+00:00", "Z"),
                "recorded_at": _aware_utc(transaction.recorded_at).isoformat().replace("+00:00", "Z"),
                "legs": [
                    {
                        "transaction_leg_id": str(leg.transaction_leg_id),
                        "sequence": leg.sequence,
                        "account_id": str(leg.account_id) if leg.account_id else None,
                        "asset_id": str(leg.asset_id),
                        "quantity": canonical_quantity(leg.quantity),
                    }
                    for leg in sorted(transaction.legs, key=lambda item: item.sequence)
                ],
            }
            for transaction in ordered
        ]
    )


class _Builder:
    def __init__(self, portfolio_id: UUID, method: CostBasisMethod, assets: dict[UUID, ProjectionAsset]) -> None:
        self.portfolio_id = portfolio_id
        self.method = method
        self.assets = assets
        self.lots: dict[tuple[UUID, UUID], list[_Lot]] = {}
        self.consumptions: list[LotConsumption] = []
        self.consumption_sequence = 0

    def apply(self, transaction: ProjectionTransaction) -> None:
        owned = [leg for leg in sorted(transaction.legs, key=lambda item: item.sequence) if leg.account_id]
        if any(leg.asset_id not in self.assets or leg.quantity == 0 for leg in owned):
            raise ProjectionValidationError("journal contains an invalid projection leg")

        transferred: set[UUID] = set()
        if transaction.transaction_kind is TransactionKind.TRANSFER:
            by_asset: dict[UUID, list[ProjectionLeg]] = {}
            for leg in owned:
                by_asset.setdefault(leg.asset_id, []).append(leg)
            for asset_id, legs in by_asset.items():
                if sum((leg.quantity for leg in legs), Decimal(0)) == 0 and any(leg.quantity > 0 for leg in legs):
                    self._transfer(transaction, asset_id, legs)
                    transferred.update(leg.transaction_leg_id for leg in legs)

        remaining = [leg for leg in owned if leg.transaction_leg_id not in transferred]
        negative = [leg for leg in remaining if leg.quantity < 0]
        positive = [leg for leg in remaining if leg.quantity > 0]
        for leg in negative:
            self._consume(transaction, leg, -leg.quantity, transfer=False)
        buy_basis = self._buy_basis(transaction, positive, negative)
        for leg in positive:
            basis_asset, basis, status = buy_basis.get(leg.transaction_leg_id, self._default_basis(leg))
            self._add_lot(transaction, leg, leg.quantity, basis_asset, basis, status, None, 0)

    def _default_basis(self, leg: ProjectionLeg) -> tuple[UUID | None, Decimal | None, BasisStatus]:
        if self.assets[leg.asset_id].asset_class is AssetClass.FIAT:
            return leg.asset_id, leg.quantity, BasisStatus.KNOWN
        return None, None, BasisStatus.UNKNOWN

    def _buy_basis(
        self,
        transaction: ProjectionTransaction,
        positive: list[ProjectionLeg],
        negative: list[ProjectionLeg],
    ) -> dict[UUID, tuple[UUID | None, Decimal | None, BasisStatus]]:
        if transaction.transaction_kind is not TransactionKind.BUY:
            return {}
        acquired = [leg for leg in positive if self.assets[leg.asset_id].asset_class is not AssetClass.FIAT]
        if not acquired or len({leg.asset_id for leg in acquired}) != 1:
            return {}
        costs = [leg for leg in negative if leg.asset_id != acquired[0].asset_id]
        cost_assets = {leg.asset_id for leg in costs}
        if len(cost_assets) != 1:
            return {}
        cost_asset = next(iter(cost_assets))
        allocations = _allocate(
            sum((-leg.quantity for leg in costs), Decimal(0)),
            [leg.quantity for leg in acquired],
            self.assets[cost_asset].precision,
        )
        return {
            leg.transaction_leg_id: (cost_asset, value, BasisStatus.KNOWN)
            for leg, value in zip(acquired, allocations, strict=True)
        }

    def _transfer(self, transaction: ProjectionTransaction, asset_id: UUID, legs: list[ProjectionLeg]) -> None:
        slices: list[_Slice] = []
        for leg in (item for item in legs if item.quantity < 0):
            slices.extend(self._consume(transaction, leg, -leg.quantity, transfer=True))
        position = 0
        offset = Decimal(0)
        for leg in (item for item in legs if item.quantity > 0):
            remaining = leg.quantity
            segment = 0
            while remaining > 0:
                if position >= len(slices):
                    raise ProjectionValidationError("transfer allocation did not preserve quantity")
                source = slices[position]
                take = min(remaining, source.quantity - offset)
                basis = self._slice_basis(source, offset, take)
                self._add_lot(
                    transaction,
                    leg,
                    take,
                    source.cost_basis_asset_id,
                    basis,
                    source.basis_status,
                    source.source_lot_key,
                    segment,
                    source.acquisition_transaction_id,
                    source.acquisition_leg_id,
                    source.acquired_at,
                )
                remaining -= take
                offset += take
                segment += 1
                if offset == source.quantity:
                    position += 1
                    offset = Decimal(0)

    def _slice_basis(self, source: _Slice, offset: Decimal, quantity: Decimal) -> Decimal | None:
        if source.cost_basis is None or source.cost_basis_asset_id is None:
            return None
        if offset == 0 and quantity == source.quantity:
            return source.cost_basis
        precision = self.assets[source.cost_basis_asset_id].precision
        before = _rounded(source.cost_basis * offset / source.quantity, precision)
        after = _rounded(source.cost_basis * (offset + quantity) / source.quantity, precision)
        return after - before

    def _consume(
        self,
        transaction: ProjectionTransaction,
        leg: ProjectionLeg,
        quantity: Decimal,
        *,
        transfer: bool,
    ) -> list[_Slice]:
        assert leg.account_id is not None
        available_lots = [
            lot for lot in self.lots.get((leg.account_id, leg.asset_id), []) if lot.remaining_quantity > 0
        ]
        available = sum((lot.remaining_quantity for lot in available_lots), Decimal(0))
        if available < quantity:
            raise NegativeHoldingRejected(
                transaction_id=transaction.transaction_id,
                transaction_leg_id=leg.transaction_leg_id,
                account_id=leg.account_id,
                asset_id=leg.asset_id,
                requested_quantity=quantity,
                available_quantity=available,
            )
        ordered = sorted(
            available_lots, key=lambda lot: (lot.acquired_at, str(lot.acquisition_transaction_id), lot.lot_key)
        )
        if self.method is CostBasisMethod.FIFO:
            allocations: list[tuple[_Lot, Decimal]] = []
            remainder = quantity
            for lot in ordered:
                take = min(remainder, lot.remaining_quantity)
                if take:
                    allocations.append((lot, take))
                    remainder -= take
                if remainder == 0:
                    break
        else:
            shares = _allocate(
                quantity, [lot.remaining_quantity for lot in ordered], self.assets[leg.asset_id].precision
            )
            allocations = [(lot, share) for lot, share in zip(ordered, shares, strict=True) if share > 0]

        result: list[_Slice] = []
        for lot, take in allocations:
            basis = self._consume_basis(lot, take)
            lot.remaining_quantity -= take
            if lot.remaining_cost_basis is not None and basis is not None:
                lot.remaining_cost_basis -= basis
            result.append(
                _Slice(
                    lot.lot_key,
                    lot.acquisition_transaction_id,
                    lot.acquisition_leg_id,
                    lot.acquired_at,
                    take,
                    lot.cost_basis_asset_id,
                    basis,
                    lot.basis_status,
                )
            )
            if not transfer:
                self.consumption_sequence += 1
                self.consumptions.append(
                    LotConsumption(
                        consumption_key=_key(
                            self.method.value,
                            transaction.transaction_id,
                            leg.transaction_leg_id,
                            lot.lot_key,
                            self.consumption_sequence,
                        ),
                        disposal_transaction_id=transaction.transaction_id,
                        disposal_leg_id=leg.transaction_leg_id,
                        lot_key=lot.lot_key,
                        quantity=take,
                        cost_basis_asset_id=lot.cost_basis_asset_id,
                        allocated_cost_basis=basis,
                        basis_status=lot.basis_status,
                        sequence=self.consumption_sequence,
                    )
                )
        return result

    def _consume_basis(self, lot: _Lot, take: Decimal) -> Decimal | None:
        if lot.remaining_cost_basis is None or lot.cost_basis_asset_id is None:
            return None
        if take == lot.remaining_quantity:
            return lot.remaining_cost_basis
        return _rounded(
            lot.remaining_cost_basis * take / lot.remaining_quantity,
            self.assets[lot.cost_basis_asset_id].precision,
        )

    def _add_lot(
        self,
        transaction: ProjectionTransaction,
        leg: ProjectionLeg,
        quantity: Decimal,
        basis_asset: UUID | None,
        basis: Decimal | None,
        status: BasisStatus,
        source_lot_key: str | None,
        segment: int,
        acquisition_transaction_id: UUID | None = None,
        acquisition_leg_id: UUID | None = None,
        acquired_at: datetime | None = None,
    ) -> None:
        assert leg.account_id is not None
        if quantity <= 0:
            raise ProjectionValidationError("projected lot quantity must be positive")
        origin_transaction = acquisition_transaction_id or transaction.transaction_id
        origin_leg = acquisition_leg_id or leg.transaction_leg_id
        origin_time = acquired_at or _aware_utc(transaction.occurred_at)
        lot_key = _key(
            self.method.value,
            self.portfolio_id,
            leg.account_id,
            leg.asset_id,
            transaction.transaction_id,
            leg.transaction_leg_id,
            source_lot_key,
            segment,
        )
        self.lots.setdefault((leg.account_id, leg.asset_id), []).append(
            _Lot(
                lot_key,
                source_lot_key,
                leg.account_id,
                leg.asset_id,
                origin_transaction,
                origin_leg,
                origin_time,
                quantity,
                quantity,
                basis_asset,
                basis,
                basis,
                status,
            )
        )

    def snapshot(self, checksum: str, count: int, last_id: UUID | None) -> ProjectionSnapshot:
        remaining_lots = tuple(
            LotProjection(
                lot.lot_key,
                lot.source_lot_key,
                lot.account_id,
                lot.asset_id,
                lot.acquisition_transaction_id,
                lot.acquisition_leg_id,
                lot.acquired_at,
                lot.original_quantity,
                lot.remaining_quantity,
                lot.cost_basis_asset_id,
                lot.original_cost_basis,
                lot.remaining_cost_basis,
                lot.basis_status,
            )
            for key in sorted(self.lots, key=str)
            for lot in sorted(self.lots[key], key=lambda item: (item.acquired_at, item.lot_key))
            if lot.remaining_quantity > 0
        )
        holdings = tuple(holding for key in sorted(self.lots, key=str) if (holding := self._holding(key)).quantity > 0)
        return ProjectionSnapshot(
            self.portfolio_id,
            self.method,
            PROJECTION_VERSION,
            checksum,
            count,
            last_id,
            holdings,
            remaining_lots,
            tuple(self.consumptions),
        )

    def _holding(self, key: tuple[UUID, UUID]) -> HoldingProjection:
        lots = [lot for lot in self.lots[key] if lot.remaining_quantity > 0]
        quantity = sum((lot.remaining_quantity for lot in lots), Decimal(0))
        statuses = {lot.basis_status for lot in lots}
        basis_assets = {lot.cost_basis_asset_id for lot in lots if lot.cost_basis_asset_id}
        if lots and statuses == {BasisStatus.KNOWN} and len(basis_assets) == 1:
            status = BasisStatus.KNOWN
            basis_asset = next(iter(basis_assets))
            total_basis = sum((lot.remaining_cost_basis or Decimal(0) for lot in lots), Decimal(0))
            average = _rounded(total_basis / quantity, self.assets[basis_asset].precision)
        elif lots and statuses == {BasisStatus.UNKNOWN}:
            status, basis_asset, total_basis, average = BasisStatus.UNKNOWN, None, None, None
        else:
            status, basis_asset, total_basis, average = BasisStatus.MIXED, None, None, None
        return HoldingProjection(key[0], key[1], quantity, basis_asset, total_basis, average, status)


def rebuild_projection(
    *,
    portfolio_id: UUID,
    cost_basis_method: CostBasisMethod,
    assets: tuple[ProjectionAsset, ...],
    transactions: tuple[ProjectionTransaction, ...],
) -> ProjectionSnapshot:
    asset_map = {asset.asset_id: asset for asset in assets}
    if len(asset_map) != len(assets) or any(not 0 <= asset.precision <= 30 for asset in assets):
        raise ProjectionValidationError("projection asset inventory is invalid")
    ordered = tuple(
        sorted(
            transactions,
            key=lambda item: (_aware_utc(item.occurred_at), _aware_utc(item.recorded_at), str(item.transaction_id)),
        )
    )
    builder = _Builder(portfolio_id, cost_basis_method, asset_map)
    for transaction in ordered:
        builder.apply(transaction)
    return builder.snapshot(
        journal_checksum(ordered),
        len(ordered),
        ordered[-1].transaction_id if ordered else None,
    )
