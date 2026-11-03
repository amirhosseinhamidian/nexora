# NEX-P2-10 — Portfolio Dashboard and Accounts UI

Status: candidate

Decision date: 2026-11-03

## Outcome

The existing authenticated shell now presents a bilingual, responsive and
owner-scoped portfolio dashboard. The selected portfolio controls its analytics,
valuation health, priced-position allocation and account registry. Persian uses
RTL presentation and Persian digits; English remains LTR.

## Data and trust boundary

The browser reads the existing same-origin owner-scoped endpoints for assets,
portfolios, accounts, analytics and valuation status. Every request remains
`no-store`, derives the owner from the server-side session and accepts no browser
owner override. No new backend route, database access or TRD Bot connection is
introduced.

Financial amounts originate as canonical decimal strings. Display rounding uses
integer decimal arithmetic rather than binary floating point. Allocation includes
only positions with a positive priced market value. Missing positions are never
silently represented as zero, and incomplete or stale NAV remains visibly marked.

## User experience

The dashboard includes:

- accessible portfolio selection;
- NAV, realized/unrealized P&L and account summary cards;
- explicit fresh, stale and missing valuation counts;
- priced-position allocation with localized labels;
- responsive account cards filtered to the selected portfolio;
- bounded loading, empty, failure and retry states.

Account external references are not rendered. Exchange credentials, wallet
secrets, live actions and financial advice remain forbidden. Account mutation,
transactions, holdings, lots, import review and reconciliation UI are deferred.

## Verification and transition

Run:

```bash
python3 scripts/verify_portfolio_dashboard_accounts.py
python3 -m unittest tests/test_portfolio_dashboard_accounts_contract.py -v
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm --filter @nexora/web test:e2e
```

The only next stage is `NEX-P2-10-FREEZE`. After that Freeze, `NEX-P2-11` may
begin the transaction, holdings and reconciliation experience.
