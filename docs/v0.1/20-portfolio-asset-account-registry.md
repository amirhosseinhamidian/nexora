# NEX-P2-02 — Portfolio, Asset and Account Registry

Status: candidate
Date: 2026-10-31
Prerequisite: frozen `NEX-P2-01` at `e82731b9ab50ca7ca0911250f71bf9096a89b314`

## Outcome

P2-02 introduces the first persistent portfolio-domain aggregates. It stores
single-owner assets and identifiers, portfolios with an explicit base asset,
and manual/watch-only/Paper/Shadow accounts. It does not create transactions,
holdings, prices, valuations, or performance projections.

## Ownership and authorization

Every registry table contains a non-null `owner_id`. Cross-aggregate foreign
keys include the owner as part of the key, so an account cannot be attached to
another owner's portfolio and a portfolio cannot use another owner's base
asset. HTTP request bodies never accept an owner ID. The API derives ownership
from the authenticated opaque session and retains the Phase 1 Origin and CSRF
checks for every mutation.

Although v0.1 has exactly one Owner, this boundary is enforced in persistence
and application code rather than assumed from deployment topology.

## Lifecycle

- Assets move once from `active` to `inactive`.
- Portfolios move once from `active` to `archived`.
- Accounts move once from `active` to `closed`.
- Lifecycle mutations require the current `row_version` and increment it.
- No registry delete operation is exposed.
- A portfolio requires an active owner-scoped base asset.
- A new account requires an active owner-scoped portfolio.

Keys are stable owner-scoped slugs. Names remain mutable-domain display data,
but P2-02 intentionally exposes creation, listing and terminal lifecycle only;
general editing is deferred until its audit and correction semantics are
defined.

## Asset identifiers

Supported identifier schemes are ISO 4217, ticker, CoinGecko, ISIN, CUSIP,
FIGI and manual. An `(owner, scheme, value)` identity is unique. Values are
bounded, validated strings and never contain exchange credentials.

## Account security boundary

An `exchange` account is descriptive only. A `wallet_watch_only` account is
also descriptive and cannot sign. The schema and request contracts contain no
API key, API secret, access token, refresh token, private key, seed phrase, or
fund-transfer capability. Unknown request fields fail validation.

## Database and API

Migration `20261031_0006` adds:

- `nexora.assets`
- `nexora.asset_identifiers`
- `nexora.portfolios`
- `nexora.accounts`

The authenticated registry endpoints are under `/v1/assets`,
`/v1/portfolios`, and `/v1/accounts`. Error responses continue to use the
versioned Phase 1 error envelope. Missing resources return an owner-opaque 404;
uniqueness, lifecycle and optimistic-concurrency conflicts return 409.

## Acceptance

P2-02 requires deterministic contract checks, backend format/lint/typecheck,
non-integration tests, PostgreSQL 17 integration tests, and the full Alembic
upgrade/downgrade/rebuild/drift cycle. Only a candidate SHA with green CI may
be frozen. P2-03 (the immutable transaction journal) remains blocked until
that Freeze.
