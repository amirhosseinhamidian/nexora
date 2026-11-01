# NEX-P2-06 — Price, FX and Manual Valuation

Status: candidate

Decision date: 2026-11-01

Prerequisite: frozen `NEX-P2-05` at `bddee3b638e67d25aaeaa1b754352b78579e5d2a`

Next allowed stage: `NEX-P2-06-FREEZE`

## Purpose

P2-06 adds immutable owner-scoped price, FX and reasoned manual valuation
evidence. It reports whether evidence is fresh, stale or missing at an explicit
`as_of` time. It does not calculate NAV, P&L, returns, allocation or tax output.

## Evidence rules

Every observation uses exact `Decimal`/PostgreSQL `Numeric(60,30)` values, an
UTC evidence time, explicit `valid_until`, source reference, source-payload
SHA-256, idempotency key and canonical request checksum. Replaying the same key
and payload returns the same immutable row; different content conflicts.

Price and FX observations plus manual valuations are protected by PostgreSQL
append-only triggers. No update or delete API exists. A manual valuation is
portfolio-scoped and requires a durable owner reason; it never rewrites source
observations. FX evidence requires two registered fiat assets, and a manual
valuation's quote asset must equal its portfolio base asset.

## Deterministic status

For a held asset and portfolio base asset, Nexora selects the latest direct
price observation whose `observed_at` is not later than `as_of`. That observation
remains selected even when stale so uncertainty cannot be hidden. A manual
valuation is used only when no eligible direct price exists. Otherwise the
result is explicitly `missing`. The portfolio base asset is returned as an
explicit identity value of one.

There is no silent forward fill, interpolation, future-evidence lookup or
implicit FX inversion. FX observations are immutable inputs; cross-currency
valuation and NAV belong to P2-07.

## Persistence

Migration `20261101_0010` adds:

- `nexora.price_observations`;
- `nexora.fx_rate_observations`;
- `nexora.manual_valuations`.

Composite owner foreign keys prevent cross-owner asset and portfolio
references. Pair/time indexes support deterministic latest-at-or-before lookup.

## Runtime API

- `POST /v1/valuation/price-observations`
- `GET /v1/valuation/price-observations`
- `POST /v1/valuation/fx-rate-observations`
- `GET /v1/valuation/fx-rate-observations`
- `POST /v1/valuation/manual-valuations`
- `GET /v1/valuation/manual-valuations`
- `GET /v1/portfolios/{portfolio_id}/valuation-status`

Writes use the existing origin, session and CSRF boundaries. Reads require the
opaque owner session. `owner_id` is never accepted from a request. Decimal
values are serialized as canonical strings and lists are deterministically
ordered and bounded to 500 rows.

## Security boundary

P2-06 adds no credentials, private keys, signing, fund transfer, live order,
direct TRD Bot database access, public hosting, autonomous AI/ML, financial
advice or tax advice capability.

## Verification

```bash
uv run python scripts/verify_holdings_projection.py
uv run python scripts/verify_valuation_evidence.py
uv run python -m unittest tests/test_valuation_evidence_contract.py -v
uv run ruff format --check apps/server alembic scripts/verify_valuation_evidence.py tests/test_valuation_evidence_contract.py
uv run ruff check apps/server alembic scripts/verify_valuation_evidence.py tests/test_valuation_evidence_contract.py
uv run mypy
uv run pytest -m "not integration" -q
uv run alembic upgrade head
uv run pytest apps/server/tests/test_postgresql_integration.py -m integration -q
uv run alembic downgrade base
uv run alembic upgrade head
uv run alembic check
```

After all checks are green on one candidate SHA, a separate P2-06 Freeze commit
may bind the evidence and open only `NEX-P2-07`.
