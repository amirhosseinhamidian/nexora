# ADR 0027: Phase 1 final acceptance evidence

- Status: Candidate for NEX-P1-13
- Date: 2026-10-28
- Decision: NEX-P1-13

## Context

P1-12 froze the complete Phase 1 implementation boundary but intentionally
deferred reference-host capacity, backup/restore, retention and final lifecycle
evidence. Passing CI alone cannot prove those host-dependent operations.

The owner does not currently require remote access. Requiring an overlay client
for a same-machine reference host would add operational surface without adding
protection. Loopback is a narrower exposure boundary than the already frozen
private-overlay capability.

## Decision

Phase 1 acceptance uses two current, checksum-bound reports produced on one
clean candidate and one named environment: the private overload benchmark and
the private operations drill. The drill verifies matching runtime/off-site
encrypted backup copies, a restore within the four-hour RTO, credential
revocation and rotation, protected retention dry-runs, HTTPS-only deployment
and Worker restart/reclaim behavior.

The reference deployment may use either `loopback_only` or
`authenticated_private_overlay`. `loopback_only` is the default for a
single-owner, same-host installation: ingress binds exactly `127.0.0.1:443`,
remote and public access remain disabled, and TLS 1.3 is still required. An
authenticated private overlay remains supported when remote access is actually
needed. LAN, wildcard and public binds are not accepted as substitutes.

TRD Bot `0.3.0` remains incompatible with the frozen integration contract, so
the default private runtime uses `disabled_incompatible_provider`. In this mode
no provider URL or token is mounted, the readiness document reports the
intentional disablement, synchronization cannot be enqueued, and the Worker
remains alive without claiming provider jobs. Enabling the adapter requires the
separate Compose override, a `>=0.3.1,<0.4.0` provider, credentials and successful
capability negotiation. Phase 1 verifies the adapter contract and idempotency
with deterministic transports; it does not claim a live-provider smoke test.

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
