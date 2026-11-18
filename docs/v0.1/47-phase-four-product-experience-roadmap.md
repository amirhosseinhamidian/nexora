# NEX-P4-00 — Nexora v0.1 Product Experience Completion Roadmap

Status: **Frozen at candidate `1fc09c0354876d1ced6eebd7fe8d29338a8c9e8d` — P4-01 is open**

Phase 3 is complete and frozen at commit
`0c08c71ccb3a75d3dd662eb6f780a677cf25d6f1`. Its accepted candidate is
`bff9b1f3b4f84f0019eef6e25d50a22d4bc9ccb2`, and its checksummed acceptance
record is `artifacts/p3-13/phase-three-final-acceptance.json`.

Phase 4 closes the product-experience gap between the accepted backend/domain
capabilities and a usable Nexora v0.1 application. It is a delivery phase, not
product version v0.4. The product remains Nexora v0.1.0.

## Why this reconciliation exists

Phase 1 delivered the private single-owner runtime, identity, application shell,
artifact storage and operational foundation. Phase 2 delivered the Portfolio
registry, immutable accounting, imports, reconciliation, holdings, valuation,
performance and exports. Phase 3 delivered Decision Intelligence, reviews,
alerts, watchlists, outcome history and complete lineage exports.

Those phases satisfy their frozen contracts, but the current Web application is
still primarily a single routed workspace with anchor navigation. Creation and
lifecycle APIs for Assets, Portfolios and Accounts are not exposed as a complete
owner workflow. Export and settings experiences are incomplete, and the
original Nexora v0.1 product proposal's primary page structure is not yet
delivered.

P4 does not invalidate earlier acceptance. It adds the missing product layer
without reimplementing accepted domain logic.

## Source hierarchy

When sources disagree, P4 uses this order:

1. Frozen repository contracts and acceptance records define implemented domain,
   security and evidence truth.
2. `Nexora_v0.1.0_Proposal_FA.pdf` defines the intended v0.1 pages and owner
   experience.
3. `Nexora_TRD_BOT_UI_Redesign_Refactor_Proposal_v0.1_FA.pdf` supplies
   incremental frontend architecture and responsive migration guidance; it does
   not transfer TRD BOT domain ownership into Nexora.
4. `Nexora_TRD_BOT_v0.3.0_Proposal_FA.pdf` supplies ecosystem and future-product
   context; it does not silently expand the Nexora v0.1 scope.

## Product boundary

P4 must make accepted capabilities usable without direct API calls. It may repair
a proven contract defect, but it cannot introduce unrelated backend domains or
weaken immutability, owner scope, optimistic concurrency, recent
reauthentication or evidence lineage.

Still forbidden are SaaS, multi-user identity, public registration, public
Internet deployment, exchange trade credentials, wallet keys, fund transfer,
live orders, autonomous AI, ML training or inference, financial or tax advice,
and direct access to the TRD BOT database.

## Target information architecture

The authenticated application will expose these primary routes:

- `/{locale}/overview`
- `/{locale}/portfolios`
- `/{locale}/portfolios/{portfolio_id}`
- `/{locale}/transactions`
- `/{locale}/decisions`
- `/{locale}/alerts`
- `/{locale}/journal`
- `/{locale}/exports`
- `/{locale}/settings`

`/{locale}` will preserve compatibility by directing the owner to Overview.
Login and Bootstrap routes remain outside the authenticated page hierarchy.

## Mandatory experience contract

- Persian uses RTL with the Sidebar on the right; English uses LTR with the
  Sidebar on the left.
- Desktop navigation is collapsible. Mobile navigation is an accessible Drawer
  or Sheet with focus restoration and scroll locking.
- Pages use the available viewport width with logical responsive margins. A
  narrow reading width is reserved for prose and forms, not imposed on tables,
  charts or dashboards.
- A first-run Wizard creates or selects the base Asset, creates the first
  Portfolio and optionally creates an Account without direct API use.
- Persian copy avoids unnecessary English. Errors say what happened, what the
  user can do and, only when useful, expose technical details separately.
- Shared micro-components own controls, feedback, overlays, tables, responsive
  record lists, charts and comparisons. Feature pages do not create one-off
  primitives.
- Sensitive lifecycle actions use a confirmation dialog. Immutable evidence is
  not physically deleted: Portfolios archive, Assets deactivate, Accounts close,
  and Transaction or Journal corrections retain history.
- Toasts communicate transient success, warning and operation failures; inline
  form errors and persistent page errors remain in context.
- Charts are used only when they improve understanding and always have a text or
  tabular equivalent. Runtime financial views cannot fabricate demo values.
- Keyboard, screen reader, reduced motion, light/dark themes, Persian/English
  direction and mobile-to-wide viewport behavior are acceptance requirements.

## Capability ownership

| Capability | Accepted source | Current product state | P4 owner |
| --- | --- | --- | --- |
| Identity and session | P1 | Complete foundation | P4-02 integration |
| Asset, Portfolio and Account registry | P2 | Creation/lifecycle mostly backend-only | P4-03 and P4-04 |
| Portfolio analytics | P2 | Partial single-page read-only UI | P4-05 |
| Transactions, holdings and reconciliation | P2 | Partial single-page UI | P4-06 |
| Decision Intelligence | P3 | Partial single-page UI | P4-07 |
| Alerts, watchlists and outcome history | P3 | Partial single-page UI | P4-08 |
| Exports and preferences | P1–P3 | Backend and download foundation | P4-09 |
| Bilingual responsive product experience | P1–P3 | Partial | P4-01, P4-02 and P4-10 |

## Delivery roadmap

### P4-00 — Roadmap Reconciliation and Freeze

Freeze the source hierarchy, capability matrix, route map, experience contract,
security boundary, stage ownership and acceptance policy. No feature code is
authorized by the Candidate.

### P4-01 — UI Foundation and Micro Components

Deliver tokens and reusable controls for forms, feedback, overlays, responsive
data presentation, charts and comparisons. Each primitive covers keyboard,
screen reader, RTL/LTR, themes, disabled, loading, error and success states.

### P4-02 — Platform Shell, Navigation and Routes

Replace anchor navigation with real routes, a directional collapsible desktop
Sidebar, accessible mobile navigation, standard page headers and a full-width
responsive frame. Preserve authentication and session recovery.

### P4-03 — First-run Onboarding

Detect missing prerequisites and guide the owner through base Asset selection or
creation, first Portfolio creation, optional Account creation, review and safe
completion. Preserve entered state, prevent duplicate submission and recover
from conflicts, network failures and session expiry.

### P4-04 — Asset, Portfolio and Account Management

Expose existing registry lifecycles as routed management experiences. Archive,
deactivate and close actions require clear confirmation. Any rename or update API
must first be registered as a contract defect or explicit scope amendment.

### P4-05 — Portfolio Overview and Analytics

Deliver NAV, realized and unrealized P&L, valuation health, allocation, accounts,
holdings and performance with useful comparisons and charts. Fresh, stale,
missing and incomplete states remain explicit.

### P4-06 — Accounting and Reconciliation Experience

Deliver routed Transaction evidence, Holdings, Lots, projection rebuild, import
dry-run, review, atomic publication and reconciliation decisions. Immutable
journal and recent-reauthentication rules remain unchanged.

### P4-07 — Decision Intelligence Pages

Deliver routed Decision and Candidate evidence, Risk Gate explanation, Portfolio
Impact, bounded scenarios and Accept/Reject/Defer review history without creating
execution authority.

### P4-08 — Alerts, Watchlists and Outcome Journal

Deliver the routed monitoring workflow from Alert or Decision evidence through
acknowledgement, snooze, monitoring preferences and append-oriented outcome
history.

### P4-09 — Exports and Settings

Deliver export creation, private-complete/AI-safe profile selection, history,
status, verification and authenticated download. Deliver bounded owner settings
for locale, theme, timezone, navigation preference, monitoring and provider
status where existing contracts permit them.

### P4-10 — Content, Localization, Accessibility and Responsive Hardening

Audit every page against the terminology contract and plain-language policy.
Harden focus, keyboard, screen-reader labels, contrast, motion, touch targets,
mixed-direction identifiers, overflow and mobile/tablet/desktop/wide layouts.

### P4-11 — Product End-to-End Acceptance Candidate

Bind complete journeys to one candidate SHA: Bootstrap/Login, Asset, first
Portfolio, optional Account, Overview, Import/Publication, Holdings rebuild,
Decision review, Alert transition, Journal entry, Export and session recovery.
Manual visual acceptance covers Persian/English, light/dark and all target
viewports.

### P4-12 — Phase 4 Final Acceptance and Freeze

Freeze the accepted local Nexora v0.1 product experience. The acceptance record
must list every passed gate, known limitation and deferred item and must keep
`production_readiness_claimed=false`.

## Execution and change policy

Every stage follows Contract → Implementation → Review → commands delivered to
the owner → owner-run tests/builds/migrations → defect repair → Candidate commit
→ same-SHA CI → Freeze → next stage.

The assistant does not run tests, builds or migrations. The owner runs the
provided commands and returns failures for repair.

After P4-00 Freeze, a material roadmap change requires a checksummed Roadmap
Amendment describing the reason, affected stages, dependency and acceptance
impact. Informal scope drift is not allowed.

## P4-00 transition

The Candidate opened only `NEX-P4-00-FREEZE`. Successful same-SHA CI is bound in
`artifacts/p4-00/phase-four-product-experience-roadmap-freeze.json`, so
`NEX-P4-01` is now open. The final Persian Word roadmap was generated from the
Frozen P4-00 source.

The private German VPS acceptance gate remains unchanged and continues to block
v0.1 production deployment and release.
