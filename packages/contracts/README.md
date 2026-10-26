# Nexora contracts package

NEX-P1-07 generates runtime API bindings deterministically from the canonical
Pydantic models. JSON Schema and OpenAPI snapshots live under
`contracts/runtime/v1`; TypeScript bindings live under `src/generated`.

Run `uv run python scripts/generate_runtime_contracts.py --check` from the
repository root to reject schema, OpenAPI, Python-manifest or TypeScript drift.
