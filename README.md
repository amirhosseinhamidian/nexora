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

`NEX-P1-07` is frozen. It closes the runtime metadata/error/correlation,
deterministic cross-language contract, and HTTP authentication-lifecycle gaps.
It adds the versioned `/version` and `/v1/auth/*` API, durable five-minute recent
reauthentication evidence, JSON Schema/OpenAPI/Python/TypeScript generation and
drift checks. Candidate `2a40a03e5a7995e6b845b3ce73e62646449da507`
is bound to nine successful workflows. The next allowed stage is `NEX-P1-08`.

`NEX-P1-08` is frozen. It closes the audit and observability gap with
bounded JSON logging, recursive secret redaction, route-template request
metrics, worker and database-pool metrics, dependency-aware readiness and
guarded immutable audit metadata. Public metrics and external telemetry export
remain disabled. Candidate `8aaa4b1fd8a164e325bdc7531aecf72e790df1f3`
is bound to the successful primary workflow and nine regression workflows on
the same SHA. The next allowed stage is `NEX-P1-09`.

`NEX-P1-09` is frozen. It registers the durable TRD
Bot event and snapshot handlers, persists immutable owner-scoped sync receipts,
quarantines unknown payload schemas, and atomically advances evidence,
checkpoints, outbox records and continuation jobs. Candidate
`53588b3c53a8244f59f1798a06efbe084e7516d5` is bound to the successful primary
workflow and ten regression workflows on the same SHA. The next allowed stage
is `NEX-P1-10`, which owns artifact and export storage.

`NEX-P1-10` is frozen. It adds the owner-scoped
versioned local-filesystem adapter, immutable SHA-256 manifests, atomic
directory publication, deterministic complete export bundles, bounded quota
enforcement, retention dry-runs and storage reconciliation. No public download
route or cloud-storage credential is introduced. Candidate
`707795735e156ebbd973f08709e52c5a994e2d17` is bound to the successful primary
workflow and eleven regression workflows on the same SHA. The next allowed
stage is `NEX-P1-11`, the authenticated Web shell.

`NEX-P1-11` is frozen. It adds bilingual passkey bootstrap and
login, the authenticated responsive application shell, explicit lifecycle
states, a nonce-bound production CSP, a same-origin CSRF-aware browser client,
and owner-scoped integrity-checked export downloads. Portfolio-domain pages
remain disabled until Phase 2. Candidate
`a32a4245a306173317556dcc5ecf85c22f1d4308` is bound to the successful
Authenticated Web shell workflow, including all three Playwright lifecycle
tests, and twelve regression workflows on the same SHA. The next allowed stage
is `NEX-P1-12`, private deployment and operations.

`NEX-P1-12` is frozen. It adds health-ordered private Compose operations,
a continuously running graceful Worker, bounded interactive overload, encrypted
database and artifact backup, owner-attended restore, dry-run-first retention
and capacity reporting. Candidate
`86651f1b49343e7e609ee5f671ad00eb83822ca9` is bound to the successful Private
deployment and operations workflow and thirteen regression workflows on the
same SHA. Actual host benchmark and restore-drill evidence remain deferred to
`NEX-P1-13`; production readiness is not claimed before that final acceptance
and freeze.

`NEX-P1-13` is frozen. Candidate
`61c5eba2ecf2a3696b6b60c87ecb1afb6064d26d` binds the local reference-host
capacity report, migration cycle, PostgreSQL integration, backend, Web and
browser gates to successful CI. Freeze commit
`5708a15d1c983c45885eeabdc4b3f77375cfc1d7` contains only the checksummed final
acceptance artifact. Phase 1 is complete; production deployment and v0.1 release
remain blocked by the deferred private German VPS acceptance gate.

`NEX-P2-01` is frozen. It freezes the owner-scoped portfolio language,
immutable transaction journal, derived holdings/lots, exact-decimal accounting,
valuation evidence, import/reconciliation, export-first policy and the twelve
stage Phase 2 delivery roadmap. It does not implement portfolio persistence or
claim product completion. Candidate
`5fad7e9f49a48fb3068634ee8ae6621af8cc6ec1` is bound to the successful primary
workflow and fifteen regression workflows on the same SHA. The next allowed
implementation stage is `NEX-P2-02`.

`NEX-P2-02` is frozen. It adds owner-scoped asset and identifier,
portfolio, and descriptive account registries with explicit lifecycle state,
optimistic concurrency, PostgreSQL constraints, a reversible migration, and
authenticated CSRF-protected APIs. It stores no exchange credential or wallet
signing material and does not introduce the transaction journal. Accepted
candidate `add7a7eec7226ecc62989b23cccf380c32e678d7` is bound to all 57
successful checks across the primary workflow and sixteen regression
workflows. The immutable transaction journal is now opened as `NEX-P2-03`.

`NEX-P2-03` is a candidate. It adds an owner-scoped append-only transaction
journal with exact-decimal balanced legs, mandatory source lineage, canonical
request checksums, idempotent posting, and explicit reversal/supersession
corrections. PostgreSQL rejects journal updates and deletes. Holdings, lots,
cost basis, valuation and P&L remain deferred. The only next step currently
opened is `NEX-P2-03-FREEZE`; P2-04 import and reconciliation is still blocked.

The P1-13 reference host defaults to TLS-protected `loopback_only` deployment
for same-machine personal use. Authenticated private-overlay deployment remains
available when remote access is required; LAN-only, wildcard and public binds
remain forbidden.

The private runtime defaults to `disabled_incompatible_provider` for TRD Bot
`0.3.0`; it does not mount fabricated provider credentials or claim live sync.
The versioned adapter remains fail-closed until a compatible provider release
and capability negotiation are available.

The repository contains the accepted Phase 1 runtime foundation, the frozen
Phase 2 domain contract, the frozen P2-02 registry, and the P2-03 transaction
journal candidate. It is not yet the complete portfolio application; derived
holdings and analytics remain in later Phase 2 stages.

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
uv run python scripts/generate_runtime_contracts.py --check
uv run python scripts/verify_runtime_api_auth.py
uv run python scripts/verify_audit_observability.py
uv run python scripts/verify_trd_bot_sync_runtime.py
uv run python scripts/verify_artifact_export_storage.py
uv run python scripts/verify_authenticated_web_shell.py
uv run python scripts/verify_private_deployment_operations.py
uv run python scripts/verify_phase_one_final_acceptance.py
uv run python scripts/verify_phase_two_portfolio_domain.py
uv run python scripts/verify_portfolio_registry.py
uv run python scripts/verify_transaction_journal.py
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
NEX_P1_ACCEPTANCE_FREEZE_PREREQUISITE=PASS
NEX_P1_07_RUNTIME_CONTRACT_TOOLCHAIN=PASS
NEX_P1_07_RUNTIME_API_AUTH=PASS
NEX_P1_07_FREEZE=PASS
NEX_P1_07_PREREQUISITE=PASS
NEX_P1_08_AUDIT_OBSERVABILITY=PASS
NEX_P1_08_FREEZE=PASS
NEX_P1_08_PREREQUISITE=PASS
NEX_P1_09_TRD_BOT_SYNC_RUNTIME=PASS
NEX_P1_09_FREEZE=PASS
NEX_P1_09_PREREQUISITE=PASS
NEX_P1_10_ARTIFACT_EXPORT_STORAGE=PASS
NEX_P1_10_FREEZE=PASS
NEX_P1_10_PREREQUISITE=PASS
NEX_P1_11_AUTHENTICATED_WEB_SHELL=PASS
NEX_P1_11_FREEZE=PASS
NEX_P1_11_PREREQUISITE=PASS
NEX_P1_12_PRIVATE_DEPLOYMENT_OPERATIONS=PASS
NEX_P1_12_FREEZE=PASS
NEX_P1_12_PREREQUISITE=PASS
NEX_P1_13_FINAL_ACCEPTANCE_TOOLING=PASS
NEX_P1_13_READY_FOR_CANDIDATE=PASS
NEX_P1_13_PREREQUISITE=PASS
NEX_P2_01_PORTFOLIO_DOMAIN=PASS
NEX_P2_01_FREEZE=PASS
NEX_P2_02_PORTFOLIO_REGISTRY=PASS
NEX_P2_02_FREEZE=PASS
NEX_P2_03_TRANSACTION_JOURNAL=PASS
NEX_P2_03_READY_FOR_CANDIDATE=PASS
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
- [`docs/v0.1/12-runtime-api-authentication-contract-toolchain.md`](docs/v0.1/12-runtime-api-authentication-contract-toolchain.md)
- [`docs/v0.1/13-audit-and-observability-foundation.md`](docs/v0.1/13-audit-and-observability-foundation.md)
- [`docs/v0.1/14-trd-bot-sync-runtime.md`](docs/v0.1/14-trd-bot-sync-runtime.md)
- [`docs/v0.1/15-artifact-and-export-storage.md`](docs/v0.1/15-artifact-and-export-storage.md)
- [`docs/v0.1/16-authenticated-web-application-shell.md`](docs/v0.1/16-authenticated-web-application-shell.md)
- [`docs/v0.1/17-private-deployment-and-operations.md`](docs/v0.1/17-private-deployment-and-operations.md)
- [`docs/v0.1/18-phase-one-final-acceptance.md`](docs/v0.1/18-phase-one-final-acceptance.md)
- [`docs/v0.1/19-phase-two-portfolio-domain-roadmap.md`](docs/v0.1/19-phase-two-portfolio-domain-roadmap.md)
- [`docs/v0.1/20-portfolio-asset-account-registry.md`](docs/v0.1/20-portfolio-asset-account-registry.md)
- [`docs/v0.1/21-immutable-transaction-journal.md`](docs/v0.1/21-immutable-transaction-journal.md)
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
- [`contracts/nexora-v0.1-runtime-api-auth-contract.json`](contracts/nexora-v0.1-runtime-api-auth-contract.json)
- [`contracts/nexora-v0.1-audit-observability.json`](contracts/nexora-v0.1-audit-observability.json)
- [`contracts/nexora-v0.1-trd-bot-sync-runtime.json`](contracts/nexora-v0.1-trd-bot-sync-runtime.json)
- [`contracts/nexora-v0.1-artifact-export-storage.json`](contracts/nexora-v0.1-artifact-export-storage.json)
- [`contracts/nexora-v0.1-authenticated-web-shell.json`](contracts/nexora-v0.1-authenticated-web-shell.json)
- [`contracts/nexora-v0.1-private-deployment-operations.json`](contracts/nexora-v0.1-private-deployment-operations.json)
- [`contracts/nexora-v0.1-phase-one-final-acceptance.json`](contracts/nexora-v0.1-phase-one-final-acceptance.json)
- [`contracts/nexora-v0.1-phase-two-portfolio-domain.json`](contracts/nexora-v0.1-phase-two-portfolio-domain.json)
- [`contracts/nexora-v0.1-portfolio-registry.json`](contracts/nexora-v0.1-portfolio-registry.json)
- [`contracts/nexora-v0.1-transaction-journal.json`](contracts/nexora-v0.1-transaction-journal.json)
- [`contracts/runtime/v1/`](contracts/runtime/v1/)
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
- [`artifacts/p1-07/runtime-api-auth-freeze.json`](artifacts/p1-07/runtime-api-auth-freeze.json)
- [`artifacts/p1-08/audit-observability-freeze.json`](artifacts/p1-08/audit-observability-freeze.json)
- [`artifacts/p1-09/trd-bot-sync-runtime-freeze.json`](artifacts/p1-09/trd-bot-sync-runtime-freeze.json)
- [`artifacts/p1-10/artifact-export-storage-freeze.json`](artifacts/p1-10/artifact-export-storage-freeze.json)
- [`artifacts/p1-11/authenticated-web-shell-freeze.json`](artifacts/p1-11/authenticated-web-shell-freeze.json)
- [`artifacts/p1-12/private-deployment-operations-freeze.json`](artifacts/p1-12/private-deployment-operations-freeze.json)
- [`artifacts/p1-13/phase-one-final-acceptance.json`](artifacts/p1-13/phase-one-final-acceptance.json)
- [`artifacts/p2-01/portfolio-domain-roadmap-freeze.json`](artifacts/p2-01/portfolio-domain-roadmap-freeze.json)
- [`artifacts/p2-02/portfolio-registry-freeze.json`](artifacts/p2-02/portfolio-registry-freeze.json)
