# NEX-P2-03 — Immutable Transaction Journal

Status: candidate
Date: 2026-10-31
Prerequisite: frozen `NEX-P2-02` at `db6566bc0713a8c9822f52d2b895f790440a3621`

## Outcome

P2-03 adds the owner-scoped financial event journal. A transaction is posted
once with at least two exact-decimal legs, an idempotency key, event time,
recording time and source lineage. Every asset represented in a transaction
must independently sum to zero. At least one leg belongs to an active account
inside the selected active portfolio; the balancing side may identify an
external counterparty without storing its credentials.

This stage does not calculate balances, holdings, lots, cost basis, valuation,
NAV or profit and loss. Those remain derived work in later Phase 2 stages.

## Exact decimal and balance boundary

The HTTP contract accepts quantities only as plain signed decimal strings.
Exponent notation, binary floats, zero quantities, non-finite numbers and more
than 30 decimal places are rejected. Persistence uses `NUMERIC(60, 30)` and
posting also checks each quantity against the precision declared by its asset.

Balance is defined per asset, not by converting unlike assets. A buy or sell
can therefore contain multiple pairs of legs: an asset pair and a cash pair.
This preserves exact evidence without silently introducing a price or FX
observation that P2-03 does not own.

## Immutability and correction

There are no update or delete operations for the journal. PostgreSQL triggers
also reject `UPDATE` and `DELETE` against `transactions` and
`transaction_legs`, so bypassing the API does not weaken append-only evidence.

A correction is another immutable transaction:

- a reversal derives the exact opposite legs from its target;
- a supersession posts a new balanced replacement;
- both retain a target link and an owner-supplied reason;
- an original transaction can have only one direct correction.

No in-place correction or physical deletion is supported.

## Idempotency and concurrency

`Idempotency-Key` is mandatory for every posting or correction. Nexora stores
a canonical checksum of the normalized request. Repeating the same key and
same request returns the existing transaction; reusing the key for different
content fails with a conflict. PostgreSQL unique constraints arbitrate
concurrent requests and duplicate corrections.

## API and storage

Migration `20261031_0007` adds `nexora.transactions` and
`nexora.transaction_legs`, plus the owner/account composite key required for
closed owner-scoped foreign keys. The authenticated API exposes create, list,
detail, reversal and supersession operations under `/v1/transactions`.

The next allowed step is `NEX-P2-03-FREEZE`. `NEX-P2-04` import and
reconciliation remains blocked until this candidate is accepted and frozen.
