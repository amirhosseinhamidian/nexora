# Nexora

Nexora is a single-owner personal portfolio and financial-intelligence platform.
It is an independent product that consumes versioned TRD Bot APIs and events; it
does not share the TRD Bot database and does not submit live orders in v0.1.0.

## Current delivery stage

`NEX-P0-01` freezes the initial product scope, Crypto Spot Paper/Shadow target,
system boundary, export-first policy, and AI/ML safety boundary. `NEX-P0-02` is
frozen: it selects the technical baseline, lightweight polyglot monorepo,
modular-monolith boundaries, repository layout, and bootstrap plan. The next
allowed stage is `NEX-P0-03`.

The repository currently contains governance and verification assets only. The
runtime code, database schema, authentication mechanism, and deployment topology
remain deliberately deferred. Runtime bootstrap cannot start before the final
Phase 0 freeze.

## Verify the scope contract

```bash
python3 scripts/verify_scope_contract.py
python3 scripts/verify_technical_baseline.py
python3 -m unittest discover -s tests -v
```

Expected result:

```text
NEX_P0_01_SCOPE_CONTRACT=PASS
NEX_P0_01_FREEZE=PASS
NEX_P0_02_TECHNICAL_BASELINE=PASS
NEX_P0_02_FREEZE=PASS
```

## Documents

- [`docs/v0.1/00-scope-and-system-boundary.md`](docs/v0.1/00-scope-and-system-boundary.md)
- [`docs/v0.1/01-technical-baseline-and-repository-architecture.md`](docs/v0.1/01-technical-baseline-and-repository-architecture.md)
- [`docs/adr/`](docs/adr/)
- [`contracts/nexora-v0.1-scope.json`](contracts/nexora-v0.1-scope.json)
- [`contracts/nexora-v0.1-technical-baseline.json`](contracts/nexora-v0.1-technical-baseline.json)
- [`artifacts/p0-01/scope-freeze.json`](artifacts/p0-01/scope-freeze.json)
- [`artifacts/p0-02/technical-baseline-freeze.json`](artifacts/p0-02/technical-baseline-freeze.json)
