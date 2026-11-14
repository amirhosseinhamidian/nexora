# NEX-P3-03 — Durable Decision and Event Projection

This stage turns the frozen TRD Bot v0.3.1 wire contract into an owner-scoped,
durable Nexora read model. It does not add the Decision Feed API, UI, owner
review workflow, order intent or any live-trading capability.

## Transaction and publication boundary

`decision_projection_states` stores immutable-source-derived projection
generations. Snapshot pages write only to a `staging` generation. The durable
worker persists source evidence, projection changes, the page checkpoint,
outbox messages and follow-up jobs in one PostgreSQL transaction.

The seven Decision/Alert resources must all complete before activation:

- `market_context`
- `decision_evaluation`
- `candidate`
- `risk_gate`
- `portfolio_intelligence`
- `alert`
- `alert_outcome`

The generation is activated only when every scan is complete and quarantine is
empty. Its canonical SHA-256 is recorded at activation. The next snapshot job
after `alert_outcome` is conditionally enqueued only after successful
activation, so a rejected generation cannot silently resume event publication.
The previous active generation remains available when a replacement is
rejected.

## Validation, replay and recovery

Every snapshot requires a v1 source reference, exact provider release, explicit
schema allowlist and valid source checksum. Unknown schemas, lineage conflicts
and checksum failures are quarantined. A quarantined snapshot generation cannot
be published.

Events use per-aggregate versions. Exact duplicate delivery is an idempotent
no-op. A version gap or conflicting replay is quarantined, clears the event
cursor, pauses publication and starts a complete snapshot resync. Cursor expiry
uses the same recovery chain. Staging data is never returned by the projection
repository.

The legacy frozen fixture schema and concrete TRD Bot v0.3.1 event schema are
both explicit allowlist entries. This is intentional compatibility, not an
unversioned fallback.

## Security boundary

The projection stores no service token or exchange credential and never reads
the TRD Bot database. It cannot submit orders, move funds, post accounting
transactions or treat owner review as execution authorization. All integration
remains service-to-service through the frozen versioned contract.

## Failure recovery

If CI, migration validation or the real local-provider smoke fails, do not
publish acceptance evidence and do not open `NEX-P3-04`. Correct the candidate
on the same stage, rerun all required gates, and retain any failed run as audit
history. A failed or cancelled run is not acceptance.
