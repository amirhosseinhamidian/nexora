# NEX-P1-09 — TRD Bot Sync Runtime

This stage closes `NEX-P1-GAP-005` by turning the frozen TRD Bot client and the
generic durable worker into a registered, restart-safe synchronization runtime.

## Delivered boundary

- explicit event and snapshot job types;
- capability negotiation on every claimed page;
- strict event-envelope validation and bounded pages;
- immutable owner-scoped receipts and replay conflict detection;
- append-only evidence for supported schemas;
- quarantine for unknown payload schemas;
- atomic receipt/evidence/checkpoint/outbox/continuation completion;
- deterministic recovery through full snapshots after cursor expiry;
- an explicit initial-sync CLI and a single bounded worker cycle;
- PostgreSQL 17 migration, integration test and drift gate.

The runtime is intentionally at-least-once. It never claims exactly-once
delivery, and it never stores provider credentials in jobs, receipts, logs or
browser-visible data.

## Operator flow

After applying migrations, enqueue the first cursor job for the existing owner:

```bash
uv run nexora-worker --enqueue-initial-sync OWNER_UUID
```

Run bounded cycles under a stable lease identity:

```bash
uv run nexora-worker --once --worker-id nexora-worker-1
```

The private runtime variables documented in `.env.example` must point to
read-only secret files. The worker fails closed if configuration, capability
negotiation, schema validation, lease ownership or checkpoint version changes.

## Deferred

- artifact and export download storage (`NEX-P1-10`);
- authenticated web shell (`NEX-P1-11`);
- portfolio application pages and analytics (Phase 2);
- live trading, exchange credentials, wallets and autonomous AI execution.

## Freeze evidence

Candidate `53588b3c53a8244f59f1798a06efbe084e7516d5` with commit message
`feat(nexora): implement P1-09 TRD Bot sync runtime` passed the primary
[TRD Bot sync runtime workflow](https://github.com/amirhosseinhamidian/nexora/actions/runs/40464364305)
and all ten regression workflows on the same SHA. The evidence records the
contract, backend, PostgreSQL 17 atomicity, migration-cycle and drift gates.

`NEX-P1-09` is therefore frozen. The next allowed stage is `NEX-P1-10`, which
owns artifact and export storage; this freeze does not claim production
readiness, external-provider smoke coverage or any live-trading capability.
