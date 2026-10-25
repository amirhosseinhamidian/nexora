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
The accepted candidate is bound to successful CI evidence, and the next allowed
stage is `NEX-P1-02`.

The repository now contains a runtime scaffold, not a complete application or a
production deployment. Database schema, authentication, TRD Bot runtime
integration, durable jobs, and private deployment remain deliberately deferred.

## Verify the scope contract

```bash
python3 scripts/verify_scope_contract.py
python3 scripts/verify_technical_baseline.py
python3 scripts/verify_integration_contracts.py
python3 scripts/verify_security_boundary.py
python3 scripts/verify_phase_zero_acceptance.py
python3 scripts/verify_runtime_foundation.py
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
```

## Documents

- [`docs/v0.1/00-scope-and-system-boundary.md`](docs/v0.1/00-scope-and-system-boundary.md)
- [`docs/v0.1/01-technical-baseline-and-repository-architecture.md`](docs/v0.1/01-technical-baseline-and-repository-architecture.md)
- [`docs/v0.1/02-api-event-export-contracts-and-compatibility.md`](docs/v0.1/02-api-event-export-contracts-and-compatibility.md)
- [`docs/v0.1/03-security-identity-and-private-deployment-boundary.md`](docs/v0.1/03-security-identity-and-private-deployment-boundary.md)
- [`docs/v0.1/04-phase-zero-acceptance-matrix.md`](docs/v0.1/04-phase-zero-acceptance-matrix.md)
- [`docs/v0.1/05-runtime-and-design-foundation-bootstrap.md`](docs/v0.1/05-runtime-and-design-foundation-bootstrap.md)
- [`docs/adr/`](docs/adr/)
- [`contracts/nexora-v0.1-scope.json`](contracts/nexora-v0.1-scope.json)
- [`contracts/nexora-v0.1-technical-baseline.json`](contracts/nexora-v0.1-technical-baseline.json)
- [`contracts/integration/v1/`](contracts/integration/v1/)
- [`contracts/nexora-v0.1-security-boundary.json`](contracts/nexora-v0.1-security-boundary.json)
- [`contracts/security/v1/`](contracts/security/v1/)
- [`contracts/nexora-v0.1-phase-zero-acceptance.json`](contracts/nexora-v0.1-phase-zero-acceptance.json)
- [`contracts/nexora-v0.1-runtime-foundation.json`](contracts/nexora-v0.1-runtime-foundation.json)
- [`contracts/acceptance/v1/phase-zero-traceability.json`](contracts/acceptance/v1/phase-zero-traceability.json)
- [`artifacts/p0-01/scope-freeze.json`](artifacts/p0-01/scope-freeze.json)
- [`artifacts/p0-02/technical-baseline-freeze.json`](artifacts/p0-02/technical-baseline-freeze.json)
- [`artifacts/p0-03/integration-contract-freeze.json`](artifacts/p0-03/integration-contract-freeze.json)
- [`artifacts/p0-04/security-boundary-freeze.json`](artifacts/p0-04/security-boundary-freeze.json)
- [`artifacts/p0-05/phase-zero-freeze.json`](artifacts/p0-05/phase-zero-freeze.json)
- [`artifacts/p1-01/runtime-foundation-freeze.json`](artifacts/p1-01/runtime-foundation-freeze.json)
