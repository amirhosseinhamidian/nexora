# ADR 0006: Pollable at-least-once event feed

Status: **Accepted candidate for NEX-P0-03**

## Context

Nexora v0.1 is a single-owner personal system. A broker or webhook receiver
would add operational surface before it is justified, while snapshots alone do
not preserve lifecycle order or support reliable incremental projections.

## Decision

TRD Bot exposes a pull-based, opaque-cursor event feed. Delivery is
**at least once**, ordering is guaranteed only per aggregate, and each aggregate
version is monotonic. Nexora deduplicates by `event_id` and `idempotency_key`.
It detects gaps using `aggregate.version` and pauses the affected projection
until backfill succeeds.

An expired cursor returns HTTP `410` and requires a full snapshot resync. An
unknown envelope or payload schema is quarantined and the affected projection
degrades rather than guessing. No component may claim exactly-once delivery.

## Consequences

- The initial system needs no Kafka, Redis Streams or public webhook endpoint.
- Replays and duplicate delivery are expected and testable.
- Cursor retention becomes part of the TRD Bot implementation contract.
- A future broker may be added behind the same envelope without changing domain
  meaning.
