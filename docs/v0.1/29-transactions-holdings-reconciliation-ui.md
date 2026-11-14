# NEX-P2-11 — Transactions, Holdings and Reconciliation UI

Status: frozen

Decision date: 2026-11-04

## Outcome

The authenticated bilingual shell now includes an owner-scoped accounting
workspace for the immutable transaction journal, rebuildable holdings and lots,
bounded import previews and explicit reconciliation decisions. Persian remains
RTL with Persian digits and English remains LTR.

## Journal and projection boundary

The journal experience is read-only. It presents balanced legs, correction kind,
source reference and exact canonical decimal quantities without binary floating
point conversion. In-place edit and physical delete remain unavailable.

Holdings and lots can be read or explicitly rebuilt with FIFO or weighted-average
cost basis. Every projection shows its version, journal transaction count and
journal SHA-256 checkpoint. Missing projection data is never represented as a
zero holding, and known, mixed and unknown basis states remain visible.

## Import and reconciliation workflow

CSV and Nexora JSON content first enters a mandatory dry run bounded to 1 MiB.
Normalized rows, duplicate counts, quarantine counts and the content checksum
remain reviewable before an owner reason can move the batch to reviewed state.
Publication is atomic, disallows partial or quarantined publication and requires
recent passkey authentication.

Reconciliation cases expose their durable state and optimistic row version. Each
decision requires an owner reason and recent reauthentication. Decisions append
evidence; the UI cannot apply a destructive fix or silently correct the journal.

## Data and security boundary

All requests use the existing same-origin `/api` client with `no-store`, the
server-side owner session and CSRF protection for mutations. No browser-supplied
owner ID, new backend route, direct database access or direct TRD Bot access is
introduced. Exchange credentials, wallet keys, fund transfer, live orders,
autonomous AI, ML inference, financial advice and tax advice remain forbidden.

## Verification and transition

Run:

```bash
python3 scripts/verify_transactions_holdings_reconciliation_ui.py
python3 -m unittest tests/test_transactions_holdings_reconciliation_ui_contract.py -v
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm --filter @nexora/web test:e2e
```

## Freeze

Commit `ef65e02e2d257b0f69277db19e96d23443b77ef2` is the accepted P2-11
implementation candidate. Its 26 push workflows and all 86 jobs succeeded on
their first attempt, including the dedicated Chromium browser acceptance job.
The immutable evidence is recorded in
`artifacts/p2-11/transactions-holdings-reconciliation-ui-freeze.json`.

P2-11 is frozen. The only next stage opened by this Freeze is
`NEX-P2-12 — Acceptance, Hardening and Freeze`; no production-readiness or
Phase 2 acceptance claim is made here.
