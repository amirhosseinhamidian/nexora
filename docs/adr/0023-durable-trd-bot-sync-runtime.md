# ADR 0023 — Durable TRD Bot sync runtime

Status: Frozen by NEX-P1-09
Date: 2026-10-27

## Decision

Nexora registers two explicit PostgreSQL-backed job handlers: `trd_bot.event_sync`
and `trd_bot.snapshot_sync`. Each claim negotiates the frozen integration
capabilities before reading a bounded page. Event receipts, accepted immutable
source evidence, compare-and-swap checkpoint movement, outbox evidence and the
next page job are committed with job success in one database transaction.

Delivery remains at-least-once. The owner-scoped event receipt is the replay
boundary: an identical event is a no-op, while reuse of an event ID with a
different canonical envelope fails closed. A valid envelope with an unknown
payload schema is retained as an immutable quarantined receipt and is never
projected as accepted evidence.

An expired event cursor resets only the event checkpoint and starts an ordered,
generation-isolated snapshot chain over every frozen resource type. Snapshot
pages are stored as versioned immutable evidence. Only the final resource can
schedule the deterministic event-stream resume job.

## Consequences

- Worker startup gains an explicit one-cycle runtime and an explicit initial
  enqueue command; the side-effect-free `--check` path remains unchanged.
- No Redis, broker, direct TRD Bot database access or exactly-once claim is
  introduced.
- P1-09 does not build portfolio projections or UI. Those features consume the
  evidence in later phases.
- Artifact downloads and export storage remain owned by NEX-P1-10.
