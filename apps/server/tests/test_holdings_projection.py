from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from nexora.holdings_projection import (
    BasisStatus,
    CostBasisMethod,
    HoldingProjection,
    NegativeHoldingRejected,
    ProjectionAsset,
    ProjectionLeg,
    ProjectionSnapshot,
    ProjectionTransaction,
    journal_checksum,
    rebuild_projection,
)
from nexora.portfolio_registry import AssetClass
from nexora.transaction_journal import TransactionKind

PORTFOLIO_ID = UUID("00000000-0000-0000-0000-000000000101")
ACCOUNT_ONE = UUID("00000000-0000-0000-0000-000000000201")
ACCOUNT_TWO = UUID("00000000-0000-0000-0000-000000000202")
USD = UUID("00000000-0000-0000-0000-000000000301")
BTC = UUID("00000000-0000-0000-0000-000000000302")
START = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


def _leg(sequence: int, account_id: UUID | None, asset_id: UUID, quantity: str) -> ProjectionLeg:
    return ProjectionLeg(uuid4(), sequence, account_id, asset_id, Decimal(quantity))


def _transaction(
    offset: int,
    kind: TransactionKind,
    *legs: ProjectionLeg,
) -> ProjectionTransaction:
    occurred = START + timedelta(minutes=offset)
    return ProjectionTransaction(uuid4(), kind, occurred, occurred + timedelta(seconds=1), tuple(legs))


def _assets() -> tuple[ProjectionAsset, ...]:
    return (
        ProjectionAsset(USD, AssetClass.FIAT, 2),
        ProjectionAsset(BTC, AssetClass.CRYPTO, 8),
    )


def _journal() -> tuple[ProjectionTransaction, ...]:
    return (
        _transaction(0, TransactionKind.OPENING_BALANCE, _leg(1, ACCOUNT_ONE, USD, "1000")),
        _transaction(
            1,
            TransactionKind.BUY,
            _leg(1, ACCOUNT_ONE, BTC, "10"),
            _leg(2, ACCOUNT_ONE, USD, "-100"),
        ),
        _transaction(
            2,
            TransactionKind.BUY,
            _leg(1, ACCOUNT_ONE, BTC, "5"),
            _leg(2, ACCOUNT_ONE, USD, "-75"),
        ),
        _transaction(
            3,
            TransactionKind.SELL,
            _leg(1, ACCOUNT_ONE, BTC, "-12"),
            _leg(2, ACCOUNT_ONE, USD, "240"),
        ),
    )


def _holding(snapshot: ProjectionSnapshot, account_id: UUID, asset_id: UUID) -> HoldingProjection:
    return next(item for item in snapshot.holdings if item.account_id == account_id and item.asset_id == asset_id)


def test_fifo_consumes_oldest_lots_and_preserves_exact_basis() -> None:
    snapshot = rebuild_projection(
        portfolio_id=PORTFOLIO_ID,
        cost_basis_method=CostBasisMethod.FIFO,
        assets=_assets(),
        transactions=_journal(),
    )
    bitcoin = _holding(snapshot, ACCOUNT_ONE, BTC)
    assert bitcoin.quantity == Decimal("3")
    assert bitcoin.total_cost_basis == Decimal("45")
    assert bitcoin.average_unit_cost == Decimal("15.00")
    assert bitcoin.basis_status is BasisStatus.KNOWN
    assert [item.quantity for item in snapshot.consumptions if item.cost_basis_asset_id == USD][-2:] == [
        Decimal("10"),
        Decimal("2"),
    ]


def test_weighted_average_consumes_the_pool_proportionally() -> None:
    snapshot = rebuild_projection(
        portfolio_id=PORTFOLIO_ID,
        cost_basis_method=CostBasisMethod.WEIGHTED_AVERAGE,
        assets=_assets(),
        transactions=_journal(),
    )
    bitcoin = _holding(snapshot, ACCOUNT_ONE, BTC)
    assert bitcoin.quantity == Decimal("3")
    assert bitcoin.total_cost_basis == Decimal("35.00")
    assert bitcoin.average_unit_cost == Decimal("11.67")


def test_owned_account_transfer_retains_original_basis_and_acquisition_lineage() -> None:
    journal = _journal()[:2]
    transfer = _transaction(
        2,
        TransactionKind.TRANSFER,
        _leg(1, ACCOUNT_ONE, BTC, "-4"),
        _leg(2, ACCOUNT_TWO, BTC, "4"),
    )
    snapshot = rebuild_projection(
        portfolio_id=PORTFOLIO_ID,
        cost_basis_method=CostBasisMethod.FIFO,
        assets=_assets(),
        transactions=(*journal, transfer),
    )
    source = _holding(snapshot, ACCOUNT_ONE, BTC)
    destination = _holding(snapshot, ACCOUNT_TWO, BTC)
    assert (source.quantity, source.total_cost_basis) == (Decimal("6"), Decimal("60.00"))
    assert (destination.quantity, destination.total_cost_basis) == (Decimal("4"), Decimal("40.00"))
    transferred_lot = next(item for item in snapshot.lots if item.account_id == ACCOUNT_TWO)
    assert transferred_lot.source_lot_key is not None
    assert transferred_lot.acquisition_transaction_id == journal[1].transaction_id


def test_non_fiat_inflow_without_cost_evidence_remains_explicitly_unknown() -> None:
    deposit = _transaction(0, TransactionKind.DEPOSIT, _leg(1, ACCOUNT_ONE, BTC, "2"))
    snapshot = rebuild_projection(
        portfolio_id=PORTFOLIO_ID,
        cost_basis_method=CostBasisMethod.FIFO,
        assets=_assets(),
        transactions=(deposit,),
    )
    holding = _holding(snapshot, ACCOUNT_ONE, BTC)
    assert holding.basis_status is BasisStatus.UNKNOWN
    assert holding.total_cost_basis is None
    assert holding.average_unit_cost is None


def test_negative_holding_rejects_the_complete_rebuild() -> None:
    disposal = _transaction(0, TransactionKind.SELL, _leg(1, ACCOUNT_ONE, BTC, "-1"))
    with pytest.raises(NegativeHoldingRejected) as captured:
        rebuild_projection(
            portfolio_id=PORTFOLIO_ID,
            cost_basis_method=CostBasisMethod.FIFO,
            assets=_assets(),
            transactions=(disposal,),
        )
    assert captured.value.reason_code == "NEGATIVE_HOLDING_REJECTED"
    assert captured.value.available_quantity == 0


def test_journal_checksum_and_projection_output_are_order_independent() -> None:
    journal = _journal()
    assert journal_checksum(journal) == journal_checksum(tuple(reversed(journal)))
    first = rebuild_projection(
        portfolio_id=PORTFOLIO_ID,
        cost_basis_method=CostBasisMethod.FIFO,
        assets=_assets(),
        transactions=journal,
    )
    repeated = rebuild_projection(
        portfolio_id=PORTFOLIO_ID,
        cost_basis_method=CostBasisMethod.FIFO,
        assets=_assets(),
        transactions=tuple(reversed(journal)),
    )
    assert first == repeated
