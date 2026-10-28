# ADR 0027: Phase 1 final acceptance evidence

- Status: Candidate for NEX-P1-13
- Date: 2026-10-28
- Decision: NEX-P1-13

## Context

P1-12 froze the complete Phase 1 implementation boundary but intentionally
deferred reference-host capacity, backup/restore, retention and final lifecycle
evidence. Passing CI alone cannot prove those host-dependent operations.

## Decision

Phase 1 acceptance uses two current, checksum-bound reports produced on one
clean candidate and one named environment: the private overload benchmark and
the private operations drill. The drill verifies matching runtime/off-site
encrypted backup copies, a restore within the four-hour RTO, credential
revocation and rotation, protected retention dry-runs, HTTPS-only deployment
and Worker restart/reclaim behavior.

The final runner rejects detached or dirty worktrees, evidence older than seven
days, candidate or environment drift, non-successful GitHub Actions and any
database except the disposable `nexora_acceptance` database. It reruns contract,
backend, migration, PostgreSQL, frontend and browser gates and records safe
command metadata without DSNs or command output.

## Consequences

The successful runner creates one checksummed acceptance artifact. The Freeze
commit may contain only that artifact. Freeze does not deploy, tag, publish,
enable public hosting or complete the Portfolio product; it closes Phase 1
foundation work and opens `NEX-P2-01`.
