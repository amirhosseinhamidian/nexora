# NEX-P2-05 — Holdings, Lots and Cost Basis

Status: candidate

Decision date: 2026-11-01

Prerequisite: frozen `NEX-P2-04` at `751ada7dc4226745e894fdc630b8d2e92eff1f36`

Next allowed stage: `NEX-P2-05-FREEZE`

## Purpose

P2-05 derives owner-scoped holdings and cost-basis lots from the immutable
transaction journal. The output is a replaceable projection, never a second
source of truth. A rebuild is identified by the journal SHA-256, projection
version, portfolio and selected method, so repeating the same rebuild is
idempotent and produces the same financial result.

This stage implements FIFO and weighted-average basis. It does not implement
prices, FX, NAV, realized or unrealized P&L, tax rules or financial advice;
those remain blocked for P2-06 and P2-07.

## Deterministic accounting rules

Transactions are processed by `occurred_at`, then `recorded_at`, then stable
transaction ID. Legs use their journal sequence. All quantities use `Decimal`;
binary floating point is absent from financial calculations and storage.

Rounding is explicit half-even at the precision of the basis asset. Allocation
preserves the original exact total by assigning any deterministic remainder to
the final slice. Unknown cost evidence remains `unknown`; Nexora does not infer
a cost that the journal did not provide.

FIFO consumes the oldest available lots. Weighted average removes quantity and
basis proportionally across the available pool. Both methods retain complete
lot-consumption lineage.

## Transfers and negative holdings

A balanced transfer between two accounts owned by the same owner retains the
original acquisition transaction, acquisition leg and cost basis. It creates
new destination lot slices linked through `source_lot_key` and does not create
disposal consumption evidence.

If a transaction would consume more than the available account/asset quantity,
the complete rebuild is rejected. Existing successful projection rows are not
partially replaced. The rejected attempt and its reason code
`NEGATIVE_HOLDING_REJECTED` are persisted separately, and the issue row is
protected by an append-only database trigger.

## Persistence and atomicity

Migration `20261101_0009` adds:

- `nexora.holdings_rebuilds` for versioned checkpoints;
- `nexora.holding_projections` for account/asset balances;
- `nexora.lot_projections` for remaining acquisition lots;
- `nexora.lot_consumptions` for disposal allocation lineage;
- `nexora.holdings_rebuild_issues` for immutable rejection evidence.

Successful rows for one portfolio and method are replaced in one transaction.
The repository locks the owner-scoped portfolio while taking the journal
snapshot and checks the checksum again before publication. A journal change
during computation fails closed with a conflict instead of publishing a mixed
checkpoint.

## Runtime API

All operations derive `owner_id` from the opaque owner session. The rebuild is
protected by the existing exact-origin and CSRF boundary. Decimal values are
serialized as canonical strings.

- `POST /v1/portfolios/{portfolio_id}/holdings/rebuilds`
- `GET /v1/portfolios/{portfolio_id}/holdings`
- `GET /v1/portfolios/{portfolio_id}/lots`

The response includes the projection version, journal checksum, transaction
count, last transaction, rebuild time and stable lot lineage. No request may
override the authenticated owner.

## Security boundary

P2-05 adds no exchange credential, private key, wallet signing, fund transfer,
live order, direct TRD Bot database access, autonomous AI/ML decision or tax or
financial advice capability. It remains a private, single-owner accounting
projection.

## Verification

Run:

```bash
uv run python scripts/verify_holdings_projection.py
uv run python -m unittest tests/test_holdings_projection_contract.py -v
uv run ruff format --check apps/server alembic scripts/verify_holdings_projection.py tests/test_holdings_projection_contract.py
uv run ruff check apps/server alembic scripts/verify_holdings_projection.py tests/test_holdings_projection_contract.py
uv run mypy
uv run pytest -m "not integration" -q
uv run alembic upgrade head
uv run pytest apps/server/tests/test_postgresql_integration.py -m integration -q
uv run alembic downgrade base
uv run alembic upgrade head
uv run alembic check
```

After the candidate SHA and all GitHub Actions checks are green, a separate
P2-05 Freeze commit may bind that evidence and open only `NEX-P2-06`.
