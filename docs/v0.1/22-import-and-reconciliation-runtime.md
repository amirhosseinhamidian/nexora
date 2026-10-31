# NEX-P2-04 — Import and Reconciliation Runtime

Status: candidate
Date: 2026-10-31
Prerequisite: frozen `NEX-P2-03` at `35572e1fba3c023e512ef2e101749fc77df29e41`

## Outcome

P2-04 adds bounded CSV and Nexora JSON transaction imports. Every request is a
dry run first. Nexora records the content SHA-256, normalizes rows
deterministically, computes a canonical row fingerprint and classifies each row
as ready, duplicate or quarantined before any journal append is possible.

The batch boundary is atomic: a quarantined batch cannot be reviewed or
published, owner review is mandatory, and all ready rows are appended to the
immutable transaction journal in one PostgreSQL transaction. Repeating the
same content returns the existing batch. Duplicate rows are retained as
explicit evidence and never silently appended twice.

## Frozen input boundary

The initial formats are:

- CSV with the exact header `row_id,portfolio_id,transaction_kind,occurred_at,memo,legs`;
- Nexora JSON with schema `nexora-transaction-import-v1`.

Content is limited to 1 MiB and 5,000 rows. Quantities remain exact decimal
strings and every normalized transaction must satisfy the P2-03 balance,
portfolio, account, asset and precision invariants. Unknown root or leg fields
are quarantined; unknown document schemas are rejected fail-closed.

## Reconciliation evidence

Duplicate and invalid rows create explicit reconciliation cases. The supported
states are open, matched, accepted difference, resolved and ignored with
reason. State changes use optimistic concurrency and every decision appends an
immutable evidence row with an owner-supplied reason. Publication and
reconciliation decisions require recent reauthentication.

No reconciliation action edits or deletes an existing transaction. Financial
corrections continue to use the P2-03 reversal or supersession flow. Automatic
destructive fixes are forbidden.

## Persistence and API

Migration `20261031_0008` adds owner-scoped import batches, normalized rows,
reconciliation cases and append-only reconciliation decisions. The API exposes
dry-run creation, batch listing/detail, owner review, atomic publication, case
listing and reasoned decisions under `/v1/imports` and
`/v1/reconciliation-cases`.

This stage does not add holdings, lots, cost basis, valuation, P&L, TRD Bot
projection, exchange credentials, wallet signing or live orders.

## Verification

Run:

```bash
uv run python scripts/verify_import_reconciliation.py
uv run python -m unittest tests/test_import_reconciliation_contract.py -v
uv run pytest -m "not integration" -q
```

After the candidate and its CI are accepted, a separate P2-04 Freeze commit
may open `NEX-P2-05` for rebuildable holdings, lots and cost basis.
