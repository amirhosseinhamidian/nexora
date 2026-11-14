# NEX-P3-00 — Phase 3 Roadmap and Deferred Deployment Amendment

Status: **Frozen — `NEX-P3-01` is the only opened implementation stage**

Phase 2 is complete and frozen. Nexora may continue bounded local development
without a VPS, but the existing `NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE` gate is
not removed, passed or bypassed. It remains blocking for v0.1 production
deployment and release on the planned private German VPS.

This amendment corrects the P2-12 transition language that described the server
gate as the only next operational stage. The server gate remains the only next
**deployment** stage, while `NEX-P3-00` opens the next local **development**
phase. Local acceptance can freeze implemented scope; it cannot claim
production readiness.

## Phase 2 prerequisite

The amendment is based on the immutable P2-12 acceptance record and Phase 2
Freeze commit:

- accepted candidate: `f71ef1840c09b12259ef519bd27ffd508b1913f2`;
- Phase 2 Freeze: `ffe5b1b50c6eb7b09bfe052ad96038de47b779df`;
- acceptance record: `artifacts/p2-12/phase-two-final-acceptance.json`;
- `phase_two_scope_accepted=true`;
- `ready_to_freeze_phase_two=true`;
- `production_readiness_claimed=false`.

## Freeze evidence

Candidate `d4478b400d5bcadf9984a4eb89dc346d73d94fb4` with tree
`c9f7db0256f10cd0a6d14462812dc2de5c487635` passed the dedicated Phase 3
roadmap workflow and all 28 regression workflows on the same SHA. The primary
push run is
`https://github.com/amirhosseinhamidian/nexora/actions/runs/41855005092`.

The checksummed evidence is recorded in
`artifacts/p3-00/phase-three-roadmap-freeze.json`. This Freeze authorizes only
the bounded local development described here. It does not pass the deferred
server gate or claim production readiness.

## Phase 3 objective

Phase 3 is **Decision Intelligence Experience**. It turns portfolio evidence and
compatible TRD Bot outputs into an explainable owner-reviewed daily workflow:

1. inspect a decision or Candidate and its immutable source evidence;
2. understand Risk Gate policy, reason codes and uncertainty;
3. inspect bounded advisory impact on the personal, Paper or Shadow Portfolio;
4. accept, reject or defer as an explicit human review;
5. monitor alerts and watchlists;
6. link the decision to an append-oriented outcome journal;
7. export the complete lineage in private-complete and AI-safe profiles.

Nexora does not alter TRD Bot market evidence. Human review is distinct from an
engine recommendation, and neither grants permission to submit an order.

## TRD Bot dependency

TRD Bot `0.3.0` remains incompatible. `NEX-P3-02` freezes the integration
contract for target release `0.3.1`. Contract and fixture-backed work may proceed
before that provider exists, but `NEX-P3-03` cannot freeze until a compatible
provider passes capability negotiation, contract tests and a real integration
smoke.

Required integration capabilities include versioned capability discovery,
Decision/Candidate/Alert snapshots, durable event pagination with cursors,
source references and checksums, versioned envelopes, idempotent human-review
commands, optimistic concurrency, export manifests, full resync, gap recovery
and service-to-service authentication. Direct database access remains
forbidden.

## Delivery roadmap

### P3-00 — Roadmap and Deferred Deployment Amendment

Freeze this development/deployment distinction, Phase 3 order, acceptance
boundary and TRD Bot dependency.

### P3-01 — Decision, Review and Journal Domain Freeze

Freeze decision evidence, owner review, alert, watchlist and outcome-journal
invariants before persistence work.

### P3-02 — TRD Bot v0.3.1 Integration Contract

Freeze capabilities, snapshots, events, review commands, resync and service
authentication shared by both repositories.

### P3-03 — Durable Decision and Event Projection

Project compatible evidence with cursor checkpoints, idempotent replay,
quarantine, gap detection and full-resync recovery.

### P3-04 — Decision Feed and Candidate Details

Expose owner-scoped Decision and Candidate evidence with complete source
references and explicit provider/degraded states.

### P3-05 — Risk Gate Explanation and Reason Codes

Show policy version, checksum, uncertainty and all approval, rejection or
deferral reasons without reimplementing the TRD Bot Risk Engine.

### P3-06 — Portfolio Candidate Impact and Bounded What-if

Show advisory exposure, concentration and bounded scenario effects for
personal, Paper and Shadow Portfolios. No order intent is created.

### P3-07 — Human Accept, Reject and Defer Workflow

Persist idempotent owner reviews with reason, evidence version, time and
optimistic concurrency. Review is not execution authorization.

### P3-08 — Alert Inbox, Acknowledge and Snooze

Deliver a durable owner-scoped alert lifecycle without mutating source events.

### P3-09 — Watchlist and Monitoring Preferences

Persist owner watchlists and bounded presentation or monitoring preferences.

### P3-10 — Decision and Outcome Journal

Link decisions, reviews, observed outcomes and owner notes without rewriting
historical evidence.

### P3-11 — Phase 3 Export Coverage

Extend private-complete and AI-safe exports across Decisions, reviews, alerts,
watchlists, journal entries and outcome history with source checksums.

### P3-12 — UI Integration, Accessibility and End-to-end

Deliver the bilingual responsive workflow with keyboard support and explicit
loading, empty, error and degraded states.

### P3-13 — Phase 3 Acceptance and Freeze

Bind migrations, PostgreSQL projection recovery, duplicate/replay behavior,
exports, accessibility, browser tests, fixture E2E and compatible-provider
smoke evidence to one candidate SHA.

## Acceptance boundary

Phase 3 cannot freeze without:

- migration from zero and migration-drift checks;
- backend, PostgreSQL, frontend and browser gates;
- schema and contract drift checks;
- duplicate delivery, replay, gap and full-resync recovery evidence;
- fixture-backed end-to-end acceptance;
- a real compatible-provider integration smoke;
- verified private-complete and AI-safe exports;
- accessibility and security inventories;
- `production_readiness_claimed=false`.

## Preserved server gate

The private-VPS gate still requires authenticated private access, TLS,
encrypted backup, an independently administered off-host copy, restore drill,
post-restore session/service-token revocation, capacity and overload evidence,
Worker recovery, retention verification and security review. A local run cannot
satisfy it.

Until that gate passes:

- production deployment remains blocked;
- the v0.1 release remains blocked;
- `NEX-DEBT-P1-13-001` remains open;
- public, SaaS, multi-user, live-trading and autonomous-AI readiness remain
  unclaimed.

## Explicitly outside Phase 3

- public Internet deployment;
- SaaS, team access or multi-user identity;
- exchange credentials, wallet keys, signing or fund transfer;
- live order submission, cancellation or modification;
- autonomous AI actions, ML training or ML inference;
- financial or tax advice;
- direct access to the TRD Bot database;
- declaring v0.1 production-ready before the private-VPS gate passes.

## Verification and transition

Run:

```bash
uv run python scripts/verify_phase_three_roadmap.py
uv run python -m unittest tests/test_phase_three_roadmap.py -v
```

The accepted candidate passed its dedicated workflow and all repository
regressions on one SHA. `NEX-P3-00` is frozen; the only opened implementation
stage is `NEX-P3-01`.
