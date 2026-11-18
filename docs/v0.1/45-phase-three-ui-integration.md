# NEX-P3-12 — UI Integration, Accessibility and End-to-end

Status: **Accepted — same-SHA CI passed at `7fb3a707dc6b3c059eb2e65b06490385f18c3b1b`**

P3-12 integrates the Phase 3 Decision Intelligence experience inside the
existing authenticated, single-owner shell. It adds no backend route, database
table or migration.

## Integrated workflow

The Decision feed, Candidate details, Risk Gate explanation, Portfolio impact,
human review, Outcome Journal, Alert Inbox and watchlists now form one bounded
workspace. Selecting Candidate or Decision evidence publishes its Decision
context to the journal, so the owner can move from immutable provider evidence
to append-only outcome history without copying an identifier between panels.

Provider source checksums, policy lineage, explicit uncertainty, local review
history and Alert history remain visible. Reviews, alerts, watchlists and journal
entries remain evidence or presentation metadata; none can authorize execution,
create an OrderIntent, post a Transaction, submit an order or move funds.

## Accessibility and responsive behavior

The integrated workspace is bilingual: Persian uses RTL and English uses LTR.
Decision evidence supports Arrow Up, Arrow Down, Home and End navigation while
retaining normal button activation. Status changes are announced through live
regions, all interactive controls receive a visible focus ring and a minimum
44 CSS-pixel target, and reduced-motion preferences suppress nonessential
animation.

Desktop, tablet and mobile layouts retain semantic headings and labelled forms.
The mobile browser fixture asserts that the document does not gain horizontal
page overflow.

## Explicit states

Loading, ready, empty, error, degraded, mutation-pending and idempotent retry
states remain explicit. Provider degradation never fabricates evidence. Failed
mutations preserve the visible evidence, and an unchanged retry retains the
same idempotency key.

## End-to-end acceptance

The Chromium suite uses same-origin fixtures for the authenticated owner
session and Phase 3 APIs. It covers the Candidate → Risk/Impact/Review → Journal
path, keyboard context changes, Persian RTL, English LTR, mobile layout, alerts,
watchlists, and explicit degraded, empty and error states. The browser gate does
not require a running provider or database.

Run:

```bash
python3 scripts/verify_phase_three_ui_integration.py
python3 -m unittest tests/test_phase_three_ui_integration_contract.py -v
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm --filter @nexora/web test:e2e
```

## Transition

P3-12 passed its dedicated workflow and regression gates at
`7fb3a707dc6b3c059eb2e65b06490385f18c3b1b`. This acceptance opens only
`NEX-P3-13 — Phase 3 Acceptance and Freeze`. Production readiness and the
private-server deployment gate remain explicitly unsatisfied.
