# Nexora

Nexora is a single-owner personal portfolio and financial-intelligence platform.
It is an independent product that consumes versioned TRD Bot APIs and events; it
does not share the TRD Bot database and does not submit live orders in v0.1.0.

## Current delivery stage

`NEX-P0-01` freezes the initial product scope, Crypto Spot Paper/Shadow target,
system boundary, export-first policy, and AI/ML safety boundary.

The repository currently contains governance and verification assets only. The
application stack, runtime code, database schema, and deployment topology are
deliberately deferred to later Phase 0 decisions.

## Verify the scope contract

```bash
python3 scripts/verify_scope_contract.py
python3 -m unittest discover -s tests -v
```

Expected result:

```text
NEX_P0_01_SCOPE_CONTRACT=PASS
```

## Documents

- [`docs/v0.1/00-scope-and-system-boundary.md`](docs/v0.1/00-scope-and-system-boundary.md)
- [`contracts/nexora-v0.1-scope.json`](contracts/nexora-v0.1-scope.json)
