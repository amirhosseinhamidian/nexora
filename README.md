# Nexora

Nexora is a single-owner personal portfolio and financial-intelligence platform.
It is an independent product that consumes versioned TRD Bot APIs and events; it
does not share the TRD Bot database and does not submit live orders in v0.1.0.

## Current delivery stage

`NEX-P0-01` freezes the initial product scope, Crypto Spot Paper/Shadow target,
system boundary, export-first policy, and AI/ML safety boundary. `NEX-P0-02` is
frozen: it selects the technical baseline, lightweight polyglot monorepo,
modular-monolith boundaries, repository layout, and bootstrap plan.
`NEX-P0-03` is frozen: it defines the versioned TRD Bot API/event/export
boundary, compatibility matrix, deterministic fixtures, and failure semantics.
`NEX-P0-04` is frozen: it defines passkey-first single-owner identity,
server-side sessions, scoped TRD Bot service authentication, secret handling,
encrypted recovery, the private-only production topology, measurable SLO and
capacity budgets, retention, and bounded artifact storage. `NEX-P0-05` is frozen:
it adds the Phase 0 acceptance and traceability matrix, resolves or transfers
every declared debt, verifies the complete P0-01 through P0-04 freeze chain, and
binds the accepted candidate to successful CI evidence. Phase 0 is complete.

`NEX-P1-01` is frozen. It bootstraps exact Node.js,
pnpm, Python, and uv toolchains; committed JavaScript and Python lockfiles; a
Next.js web shell; minimal FastAPI and inert worker entry points; pinned
containers; and a bilingual light/dark design foundation. Persian is RTL with a
local Vazirmatn variable font, while English is LTR with self-hosted Inter.
The accepted candidate is bound to successful CI evidence.

`NEX-P1-02` is frozen. It adds one immutable,
allowlisted and fail-closed runtime configuration model plus an explicit shared
composition factory for the API and inert worker. Configuration fingerprints
are deterministic and contain no secrets. The accepted candidate is bound to
successful CI evidence.

`NEX-P1-03` is frozen. It adds the owner-aware
PostgreSQL 17 persistence spine, private file-based migration configuration,
SQLAlchemy 2 models, reversible Alembic migrations, immutable source-evidence
enforcement, and the complete migration-cycle CI gate. The accepted candidate
is bound to successful database and regression CI evidence.

`NEX-P1-04` is frozen. It implements the typed, fail-closed TRD Bot HTTP
adapter, exact capability negotiation, strict schema validation, private
file-based endpoint/token configuration and bounded retry semantics for all
eight frozen integration operations. TRD Bot 0.3.0 remains incompatible. The
adapter is deliberately not registered in runtime composition; durable sync
execution belongs to P1-05. The accepted candidate is bound to successful
adapter, backend, web, contract and PostgreSQL CI evidence. The next allowed
stage is `NEX-P1-05`.

`NEX-P1-05` is frozen. It adds PostgreSQL-backed
durable jobs, optimistic projection checkpoints, and a transactional outbox;
bounded `SKIP LOCKED` claims; expiring leases and restart reclaim; deterministic
retry/dead-letter behavior; and an explicit handler-based worker engine. The
delivery model is at-least-once. No live provider handler, exchange credential,
or live-order capability is registered. The accepted candidate is bound to
successful durable-work, PostgreSQL, backend and regression CI evidence. The
next allowed stage is `NEX-P1-06`.

`NEX-P1-06` is frozen. It adds the single-owner passkey identity runtime,
cryptographic WebAuthn verification restricted to ES256/EdDSA, single-use
bootstrap and recovery, opaque server-side sessions, scoped service-token
metadata, immutable security audit evidence, and a private single-host Compose
topology that exposes only HTTPS 443. The accepted candidate is bound to the
identity, PostgreSQL, private-topology, backend and regression CI evidence on
the same commit. The next allowed stage is `NEX-P1-ACCEPTANCE`; production
readiness remains unclaimed until that acceptance succeeds.

`NEX-P1-ACCEPTANCE` roadmap reconciliation is frozen, not a final acceptance
claim. It compares the six frozen delivery milestones with the
original twelve-stage Phase 1 roadmap, keeps nine missing or partial capability
groups blocking, and records an owned continuation from `NEX-P1-07` through
`NEX-P1-13`. The freeze is bound to candidate
`ab41a7dba49871fdce5cf0ad72fa0e06a6d927e7` and eight successful workflows.
Its next allowed stage is `NEX-P1-07`; Phase 1 remains incomplete.

The repository now contains the Phase 1 runtime foundation, not the complete
portfolio application. Scheduled TRD Bot synchronization, portfolio-domain
features and final production acceptance remain deliberately deferred.

## Verify the scope contract

```bash
python3 scripts/verify_scope_contract.py
python3 scripts/verify_technical_baseline.py
python3 scripts/verify_integration_contracts.py
python3 scripts/verify_security_boundary.py
python3 scripts/verify_phase_zero_acceptance.py
python3 scripts/verify_runtime_foundation.py
python3 scripts/verify_application_composition.py
python3 scripts/verify_postgresql_schema.py
python3 scripts/verify_trd_bot_adapter.py
python3 scripts/verify_durable_jobs_outbox.py
python3 scripts/verify_single_owner_identity_runtime.py
python3 scripts/verify_phase_one_readiness.py
python3 -m unittest discover -s tests -v
```

Expected result:

```text
NEX_P0_01_SCOPE_CONTRACT=PASS
NEX_P0_01_FREEZE=PASS
NEX_P0_02_TECHNICAL_BASELINE=PASS
NEX_P0_02_FREEZE=PASS
NEX_P0_03_INTEGRATION_CONTRACT=PASS
NEX_P0_03_FREEZE=PASS
NEX_P0_04_SECURITY_BOUNDARY=PASS
NEX_P0_04_FREEZE=PASS
NEX_P0_04_PREREQUISITE=PASS
NEX_P0_05_PHASE_ZERO_ACCEPTANCE=PASS
NEX_P0_05_FREEZE=PASS
NEX_P0_05_PREREQUISITE=PASS
NEX_P1_01_RUNTIME_FOUNDATION=PASS
NEX_P1_01_FREEZE=PASS
NEX_P1_01_PREREQUISITE=PASS
NEX_P1_02_APPLICATION_COMPOSITION=PASS
NEX_P1_02_FREEZE=PASS
NEX_P1_02_PREREQUISITE=PASS
NEX_P1_03_POSTGRESQL_SCHEMA=PASS
NEX_P1_03_FREEZE=PASS
NEX_P1_03_PREREQUISITE=PASS
NEX_P1_04_TRD_BOT_ADAPTER=PASS
NEX_P1_04_FREEZE=PASS
NEX_P1_04_PREREQUISITE=PASS
NEX_P1_05_DURABLE_JOBS_OUTBOX=PASS
NEX_P1_05_FREEZE=PASS
NEX_P1_05_PREREQUISITE=PASS
NEX_P1_06_SINGLE_OWNER_IDENTITY_RUNTIME=PASS
NEX_P1_06_FREEZE=PASS
NEX_P1_06_PREREQUISITE=PASS
NEX_P1_ACCEPTANCE_RECONCILIATION=PASS
NEX_P1_ACCEPTANCE_FREEZE=PASS
```

## Documents

- [`docs/v0.1/00-scope-and-system-boundary.md`](docs/v0.1/00-scope-and-system-boundary.md)
- [`docs/v0.1/01-technical-baseline-and-repository-architecture.md`](docs/v0.1/01-technical-baseline-and-repository-architecture.md)
- [`docs/v0.1/02-api-event-export-contracts-and-compatibility.md`](docs/v0.1/02-api-event-export-contracts-and-compatibility.md)
- [`docs/v0.1/03-security-identity-and-private-deployment-boundary.md`](docs/v0.1/03-security-identity-and-private-deployment-boundary.md)
- [`docs/v0.1/04-phase-zero-acceptance-matrix.md`](docs/v0.1/04-phase-zero-acceptance-matrix.md)
- [`docs/v0.1/05-runtime-and-design-foundation-bootstrap.md`](docs/v0.1/05-runtime-and-design-foundation-bootstrap.md)
- [`docs/v0.1/06-application-composition-and-runtime-configuration.md`](docs/v0.1/06-application-composition-and-runtime-configuration.md)
- [`docs/v0.1/07-postgresql-schema-and-migrations.md`](docs/v0.1/07-postgresql-schema-and-migrations.md)
- [`docs/v0.1/08-versioned-trd-bot-adapter.md`](docs/v0.1/08-versioned-trd-bot-adapter.md)
- [`docs/v0.1/09-durable-jobs-checkpoints-and-outbox.md`](docs/v0.1/09-durable-jobs-checkpoints-and-outbox.md)
- [`docs/v0.1/10-single-owner-identity-session-private-runtime.md`](docs/v0.1/10-single-owner-identity-session-private-runtime.md)
- [`docs/v0.1/11-phase-one-roadmap-reconciliation.md`](docs/v0.1/11-phase-one-roadmap-reconciliation.md)
- [`docs/adr/`](docs/adr/)
- [`contracts/nexora-v0.1-scope.json`](contracts/nexora-v0.1-scope.json)
- [`contracts/nexora-v0.1-technical-baseline.json`](contracts/nexora-v0.1-technical-baseline.json)
- [`contracts/integration/v1/`](contracts/integration/v1/)
- [`contracts/nexora-v0.1-security-boundary.json`](contracts/nexora-v0.1-security-boundary.json)
- [`contracts/security/v1/`](contracts/security/v1/)
- [`contracts/nexora-v0.1-phase-zero-acceptance.json`](contracts/nexora-v0.1-phase-zero-acceptance.json)
- [`contracts/nexora-v0.1-runtime-foundation.json`](contracts/nexora-v0.1-runtime-foundation.json)
- [`contracts/nexora-v0.1-application-composition.json`](contracts/nexora-v0.1-application-composition.json)
- [`contracts/nexora-v0.1-postgresql-schema.json`](contracts/nexora-v0.1-postgresql-schema.json)
- [`contracts/nexora-v0.1-trd-bot-adapter.json`](contracts/nexora-v0.1-trd-bot-adapter.json)
- [`contracts/nexora-v0.1-durable-jobs-outbox.json`](contracts/nexora-v0.1-durable-jobs-outbox.json)
- [`contracts/nexora-v0.1-single-owner-identity-runtime.json`](contracts/nexora-v0.1-single-owner-identity-runtime.json)
- [`contracts/nexora-v0.1-phase-one-readiness.json`](contracts/nexora-v0.1-phase-one-readiness.json)
- [`contracts/acceptance/v1/phase-zero-traceability.json`](contracts/acceptance/v1/phase-zero-traceability.json)
- [`artifacts/p0-01/scope-freeze.json`](artifacts/p0-01/scope-freeze.json)
- [`artifacts/p0-02/technical-baseline-freeze.json`](artifacts/p0-02/technical-baseline-freeze.json)
- [`artifacts/p0-03/integration-contract-freeze.json`](artifacts/p0-03/integration-contract-freeze.json)
- [`artifacts/p0-04/security-boundary-freeze.json`](artifacts/p0-04/security-boundary-freeze.json)
- [`artifacts/p0-05/phase-zero-freeze.json`](artifacts/p0-05/phase-zero-freeze.json)
- [`artifacts/p1-01/runtime-foundation-freeze.json`](artifacts/p1-01/runtime-foundation-freeze.json)
- [`artifacts/p1-02/application-composition-freeze.json`](artifacts/p1-02/application-composition-freeze.json)
- [`artifacts/p1-03/postgresql-schema-freeze.json`](artifacts/p1-03/postgresql-schema-freeze.json)
- [`artifacts/p1-04/trd-bot-adapter-freeze.json`](artifacts/p1-04/trd-bot-adapter-freeze.json)
- [`artifacts/p1-05/durable-jobs-outbox-freeze.json`](artifacts/p1-05/durable-jobs-outbox-freeze.json)
- [`artifacts/p1-06/single-owner-identity-runtime-freeze.json`](artifacts/p1-06/single-owner-identity-runtime-freeze.json)
- [`artifacts/p1-acceptance/phase-one-readiness-freeze.json`](artifacts/p1-acceptance/phase-one-readiness-freeze.json)
