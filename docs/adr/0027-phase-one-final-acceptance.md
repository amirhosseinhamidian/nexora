# ADR 0027: Phase 1 final acceptance evidence

- Status: Candidate for NEX-P1-13
- Date: 2026-10-28
- Decision: NEX-P1-13

## Context

P1-12 froze the complete Phase 1 implementation boundary but intentionally
deferred reference-host capacity and host-dependent operations. Passing CI
alone cannot prove either category, but the development reference host and the
future production server are different acceptance environments.

The owner does not currently require remote access. Requiring an overlay client
for a same-machine reference host would add operational surface without adding
protection. Loopback is a narrower exposure boundary than the already frozen
private-overlay capability.

## Decision

Phase 1 acceptance is split into two explicit profiles. The current
`local_reference_foundation` profile binds a checksum-protected capacity and
overload report, green CI and the complete regression suite to one clean
candidate. It may freeze the Phase 1 foundation and open `NEX-P2-01`, but it
cannot claim production readiness.

The second gate, `NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE`, is deferred until the
private German VPS exists. It remains a blocker for v0.1 production deployment
and release and owns the off-host encrypted backup, restore/RTO, retention,
server capacity, hardened remote access and post-restore lifecycle evidence.
The debt is tracked as `NEX-DEBT-P1-13-001`.

The local reference deployment uses `loopback_only`: ingress binds exactly
`127.0.0.1:443`, remote and public access remain disabled, and TLS 1.3 is still
required. A private overlay or equivalently hardened access model is selected
and verified later on the actual VPS. LAN, wildcard and accidental public binds
are not accepted as substitutes.

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

The successful local runner creates one checksummed acceptance artifact with
`production_readiness_claimed=false` and the server gate recorded as
`deferred_to_server_deployment`. The Freeze commit may contain only that
artifact. Freeze does not deploy, tag, publish, enable public hosting or complete
the Portfolio product; it closes Phase 1 foundation work and opens `NEX-P2-01`.
The later server gate must pass before v0.1 can be deployed or released.
