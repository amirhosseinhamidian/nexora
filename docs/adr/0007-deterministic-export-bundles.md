# ADR 0007: Deterministic, manifest-backed export bundles

Status: **Accepted candidate for NEX-P0-03**

## Context

Nexora must make financial, portfolio and lifecycle evidence portable for
personal review and later AI/ML analysis. Existing narrow CSV reports do not
provide complete lineage, schema identity, units, redaction information or
file integrity evidence.

## Decision

Every accepted export is complete and is accompanied by
`nexora-export-manifest-v1`. The manifest records source versions, scope,
filters, UTC timestamps, currency/unit context, lineage references, per-file
schemas and SHA-256 checksums. JSON is canonicalized using RFC 8785. Supported
formats are JSON, JSONL, CSV, Parquet and ZIP bundles; profiles are `private`
and `ai_safe`.

Partial exports are never presented as successful. Secret-bearing fields are
forbidden in every profile. The AI-safe profile additionally applies an
explicit redaction profile without destroying evidence lineage.

## Consequences

- Consumers can reproduce, verify and compare export artifacts.
- AI tools receive bounded, attributable evidence instead of database dumps.
- Export generation must be idempotent and durable in the later runtime.
- Retention and storage placement remain later operational decisions.
