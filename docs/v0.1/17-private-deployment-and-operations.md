# NEX-P1-12 — Private Deployment and Operations

NEX-P1-12 closes `NEX-P1-GAP-008`. It turns the existing private topology into
an operable single-owner runtime while preserving the P0-04 security boundary.

## Delivered

- private-overlay HTTPS 443 as the only host port;
- health-ordered Web/API/Worker/PostgreSQL startup and bounded log rotation;
- a long-running, gracefully stoppable durable Worker;
- explicit interactive overload with HTTP 429 and `Retry-After`;
- encrypted PostgreSQL plus artifact backup with atomic dual publication;
- owner-attended restore with checksum verification and credential revocation;
- dry-run-first, idempotent retention for expired unpinned exports and verified
  backup pairs outside the 14 daily, 8 weekly and 12 monthly tiers;
- capacity reporting against the frozen database, artifact and free-space limits;
- pinned operational toolchain, runbook and secret inventory without values.

## Operational boundary

The host is not highly available. Its backup copy is not off-site merely because
it is in another directory. At least one independently administered or mounted
off-host copy is required. The private age identity must not remain on the
runtime host. Backup targets RPO 24 hours and restore targets RTO four hours.

Retention never automatically deletes immutable evidence or financial records.
The current apply scope is intentionally smaller than the complete P0 retention
inventory: only expired unpinned exports and verified backup pairs outside the
declared tiers are eligible. Later data-class retention requires a separate
migration and audited policy implementation.

## Acceptance split

This stage delivers the implementation and deterministic tests. It does not
claim that a real host met the budgets. `NEX-P1-13` must bind the actual fresh
install, migration cycle, concurrency/restart tests, overload benchmark,
retention dry-run, backup/restore drill and private deployment smoke evidence to
one candidate SHA and successful CI before Phase 1 can freeze.

## Excluded

Public-internet hosting, SaaS/multi-user support, exchange credentials, wallet
operations, live orders and autonomous AI execution remain outside v0.1.
