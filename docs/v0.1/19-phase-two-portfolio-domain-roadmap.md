# NEX-P2-01 — Portfolio Domain and Phase Two Roadmap

Status: frozen
Decision date: 2026-10-29
Freeze evidence date: 2026-10-31
Next allowed stage: `NEX-P2-02`

## Purpose

Phase 1 delivered and accepted the private single-owner runtime foundation.
Phase 2 turns that foundation into the first usable Nexora portfolio product.
This decision freezes the accounting language, immutable evidence rules,
security boundary and delivery order before portfolio tables or APIs are built.

P2-01 does not claim that the portfolio product exists. It defines the contract
that P2-02 through P2-12 must implement and verify.

Candidate `5fad7e9f49a48fb3068634ee8ae6621af8cc6ec1` is bound to the successful
`Phase 2 portfolio domain` workflow and all fifteen regression workflows on the
same SHA. The checksummed Freeze record opens only `NEX-P2-02`.

## Accepted prerequisite

P2-01 is based on the Phase 1 Freeze commit
`5708a15d1c983c45885eeabdc4b3f77375cfc1d7`. That commit accepts candidate
`61c5eba2ecf2a3696b6b60c87ecb1afb6064d26d` through the checksummed P1-13
acceptance record. The local reference runtime, CI, migrations, PostgreSQL
integration, browser lifecycle and private topology gates passed.

The deferred server gate is preserved. Before v0.1 production deployment or
release, the same private topology must be accepted again on the planned German
VPS. Local development and reference-host testing may continue before that VPS
exists.

## Portfolio domain

Nexora owns a private, single-owner accounting view. The initial portfolio
kinds are personal, Paper and Shadow. Accounts can represent exchanges,
watch-only wallets, cash, manual brokerage data and simulated accounts. A
watch-only wallet never stores a seed phrase or private key.

The core model contains:

- portfolios, accounts, assets and stable asset identifiers;
- immutable transactions composed of two or more legs;
- lots and holding projections rebuilt from the transaction journal;
- immutable price and FX observations plus reasoned manual valuations;
- import batches, normalized rows and reconciliation cases;
- point-in-time valuation and performance snapshots.

Financial quantities use exact decimal representations with declared asset or
currency precision. Binary floating-point values are not allowed in financial
storage or calculations. UTC is canonical; locale affects presentation only.

## Journal and correction semantics

A posted transaction is immutable, owner-scoped, idempotent and linked to its
source evidence. It records both event time and Nexora recording time.
Correction occurs through reversal or supersession; an in-place edit is never a
valid correction. Holdings, lots, NAV and P&L are derived projections and must
remain reproducible from the journal and immutable valuation evidence.

The initial cost-basis methods are FIFO and weighted average. Transfers between
accounts owned by the same person retain basis and are not modeled as disposal.
Negative holdings are rejected and quarantined by default rather than silently
accepted. Nexora does not claim tax advice or jurisdiction-specific tax logic.

## Valuation and uncertainty

Every price, FX rate or manual valuation has a time, source reference and
lineage. Stale or missing prices remain visible. Nexora cannot silently forward
fill values without an explicit future policy. A manual valuation requires an
owner-supplied reason and never overwrites source evidence.

These rules make later AI analysis useful without teaching it that an inferred
number is an observed fact. Exported data carries lineage, missing-data state
and uncertainty alongside financial results.

## Import and reconciliation

Initial inputs are manual entry, CSV, Nexora JSON and a future compatible TRD
Bot Paper/Shadow projection. Every import starts as a dry run, normalizes
deterministically, records a content checksum, detects duplicate rows and is
safe to repeat. Unknown rows are quarantined. A batch cannot partially publish.

Differences become explicit reconciliation cases. Automatic destructive fixes
are forbidden; a correction requires owner approval and durable reason
evidence.

## Export-first boundary

Portfolio information remains exportable as JSON, CSV, Parquet and a manifest
backed ZIP bundle. Two profiles are planned:

- `private_complete` contains the complete owner-scoped financial record;
- `ai_safe` contains analysis-ready data while excluding credentials, tokens,
  recovery codes, keys, session identifiers and raw security context.

Every export is schema-versioned, checksummed and timestamped. No export is
placed in a public bucket or exposed by a public download URL.

## TRD Bot boundary

TRD Bot `0.3.0` remains an incompatible provider and the runtime stays in
`disabled_incompatible_provider` mode. P2 never reads the TRD Bot database.
When a compatible provider is released, Nexora may project Paper/Shadow
evidence through the frozen API/event/export boundary, immutable sync receipts,
schema quarantine and full-resync rules. That projection is evidence input, not
an unquestioned accounting truth. Live orders remain forbidden.

## Phase 2 delivery roadmap

### P2-01 — Portfolio Domain and Phase Two Roadmap

Freeze the domain language, accounting invariants, export policy, security
boundary and delivery order.

### P2-02 — Portfolio, Asset and Account Registry

Add owner-scoped portfolios, stable assets and identifiers, accounts, lifecycle
rules, migrations, repositories and APIs without adding a transaction journal.

### P2-03 — Immutable Transaction Journal

Add idempotent transactions and immutable balanced legs, source lineage,
reversal/supersession and PostgreSQL concurrency guarantees.

### P2-04 — Import and Reconciliation Runtime

Add dry-run CSV/JSON imports, deterministic normalization, duplicate detection,
quarantine, review and reconciliation evidence.

### P2-05 — Holdings, Lots and Cost Basis

Build rebuildable holdings and lot projections with FIFO and weighted-average
cost basis and explicit checkpoint/version semantics.

### P2-06 — Price, FX and Manual Valuation

Persist immutable price/FX evidence, reasoned manual valuations and visible
stale/missing-price states.

### P2-07 — NAV, P&L and Performance

Derive point-in-time NAV, realized/unrealized P&L and bounded performance series
without claiming tax or investment advice.

### P2-08 — TRD Bot Paper/Shadow Projection

Connect only when a compatible provider contract exists. Project Paper/Shadow
evidence through durable jobs and quarantine unknown schemas. No live execution.

### P2-09 — Portfolio API and Export

Expose owner-scoped read APIs and deterministic complete/AI-safe export bundles
with lineage, uncertainty and checksums.

### P2-10 — Portfolio Dashboard and Accounts UI

Deliver bilingual responsive portfolio overview, valuation health, allocation
and account registry experiences in the existing authenticated shell.

### P2-11 — Transactions, Holdings and Reconciliation UI

Deliver journal, holdings, lots, import preview and reconciliation workflows
with accessible Persian RTL and English LTR presentation.

### P2-12 — Acceptance, Hardening and Freeze

Bind deterministic accounting fixtures, migration cycles, PostgreSQL
concurrency, projection rebuilds, export verification, browser tests, capacity
and security inventory to one candidate SHA before Phase 2 Freeze.

## Explicitly outside Phase 2

- SaaS, multi-user identity and self-registration;
- public Internet deployment;
- exchange credentials or connected trading accounts;
- wallet private keys, signing, transfer or custody;
- live order submission, cancellation or modification;
- autonomous AI decisions or actions;
- ML training or inference;
- financial or tax advice;
- release before the private VPS deployment gate passes.

AI/ML remains a planned later program in both Nexora and TRD Bot. Phase 2
creates clean evidence, deterministic labels and exportable history for that
future work, but does not place a model in the decision or execution path.

## Verification and transition

Run:

```bash
uv run python scripts/verify_phase_two_portfolio_domain.py
uv run python -m unittest tests/test_phase_two_portfolio_domain.py -v
```

The candidate passed its dedicated GitHub Actions workflow and repository
regressions on one SHA. The Freeze record validates the exact commit, tree,
workflow runs, job IDs, contract checksum and Phase 1 prerequisite. The only
opened implementation stage is `NEX-P2-02`.
