# ADR 0019: PostgreSQL durable work coordination

- Status: Frozen by NEX-P1-05
- Date: 2026-10-25

## Context

Nexora must resume synchronization after worker restarts, avoid two workers owning
the same item concurrently, advance a source cursor without gaps, and publish
follow-up facts without a dual-write window. Phase 0 already selected PostgreSQL
as the initial durable queue and explicitly deferred Redis and a message broker.

## Decision

Use three owner-aware PostgreSQL tables: `background_jobs`,
`projection_checkpoints`, and `outbox_events`. Workers claim bounded batches with
`SELECT ... FOR UPDATE SKIP LOCKED`, receive expiring leases, and increment the
attempt number at claim time. Expired leases are reclaimable. A final expired
attempt or a final reported failure becomes `dead_letter`.

Job completion, checkpoint compare-and-swap, and outbox insertion share one
database transaction. Both jobs and outbox events use owner-scoped idempotency
keys and canonical payload SHA-256 values. Delivery is at-least-once; consumers
must be idempotent and Nexora does not claim exactly-once delivery.

The worker engine accepts an explicit handler allowlist. It never claims unknown
job types, refuses an empty registry, and stores only bounded error codes rather
than exception messages. P1-05 does not register a live TRD Bot provider handler.

## Consequences

- A restart can reclaim abandoned work without an in-memory queue.
- Concurrent workers coordinate through PostgreSQL row locks.
- Checkpoint or outbox failure rolls back job completion.
- Operational review is required for dead-letter items.
- Provider scheduling and production handler registration remain P1-06 work.
