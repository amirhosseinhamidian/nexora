# ADR 0026: Private single-host operations

- Status: Candidate
- Date: 2026-10-27
- Decision: NEX-P1-12

## Context

The frozen Phase 0 security boundary permits one privately operated host and
requires encrypted backup, bounded retention, capacity evidence and graceful
overload behavior. P1-11 supplied an authenticated Web shell but did not make
the topology operational: the Worker only ran a configuration check and there
was no restore or retention path.

## Decision

Nexora uses one Docker Compose topology on an encrypted host. Caddy is the only
service with a host port and binds 443 to an authenticated private-overlay
address. Web, API, Worker and PostgreSQL remain on internal networks. Runtime
secrets are absolute read-only files and container logs are rotated and bounded.

The Worker runs the durable single-claim loop, handles SIGTERM after its current
bounded cycle, and relies on PostgreSQL leases for reclaim. The API uses a
process-local token bucket at the frozen 10 requests/second sustained and
25-request burst limits. Excess interactive requests fail explicitly with 429
and `Retry-After`; accepted durable work and immutable evidence are not dropped.

An ephemeral operations image shares only the volumes required for its command.
It creates a PostgreSQL custom dump and artifact archive, encrypts before
publication with an age X25519 public recipient, and atomically publishes an
SHA-256 manifest to separate runtime and off-host roots. The private age identity
is offline and is mounted only for an owner-attended restore. Restore revokes
sessions and service tokens and requires token rotation before restart.

Retention is dry-run by default. An apply requires owner approval, persists an
immutable plan and emits an audit record before each deletion. It can only
delete expired unpinned exports or verified runtime/off-host backup pairs that
fall outside the 14 daily, 8 weekly and 12 monthly tiers. Pinned artifacts,
immutable evidence and mismatched backup inventories are excluded fail-closed.

## Consequences

This closes the implementation gap for private operations without claiming
production acceptance. Single-host failure tolerance remains false. P1-13 must
run and record the capacity benchmark, overload smoke test, migration cycle,
backup/restore drill and full deployment smoke test against one candidate SHA.
Public deployment, multi-user identity, exchange credentials and live execution
remain forbidden.
