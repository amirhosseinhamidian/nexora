# ADR 0017: Owner-aware PostgreSQL persistence spine

- Status: Accepted by NEX-P1-03 candidate
- Date: 2026-10-25

## Context

The frozen runtime and composition stages intentionally contain no database
adapter. P1-04 integration, P1-05 durable jobs and P1-06 identity need a small,
reversible PostgreSQL foundation without prematurely creating their tables or
allowing application startup to mutate production schema.

## Decision

Nexora uses PostgreSQL 17 with SQLAlchemy 2 models and Alembic migrations. The
first migration creates the `nexora` namespace and only three tables:
`owner_profiles`, `source_references`, and `immutable_source_evidence`.

Every application record in this migration is owner-aware. The owner key is
restricted to the single `primary_owner` row, while UUID identifiers keep a
future migration path available. External source references include source and
schema versions, correlation ID, observed time, and a SHA-256 payload checksum.
Source references and their JSONB evidence are protected from UPDATE and DELETE
by database triggers.

Migration processes read the PostgreSQL DSN from one absolute, non-symlinked,
private file named by `NEXORA_MIGRATION_DATABASE_DSN_FILE`. The DSN is never a
committed setting, command-line argument, log field, or direct environment
value. Production requires file mode `0400`; development and CI permit a
private owner-only file up to `0600`.

Database sessions pin `search_path` to `public`, while every application table
remains explicitly schema-qualified. Alembic stores its version table in
`public.alembic_version`. This prevents a PostgreSQL role named `nexora` from
silently making the application namespace the connection's default schema and
causing false foreign-key or version-table drift.
The autogenerate name filter excludes only Alembic's own version table in the
default/public namespace; application tables remain fully drift-checked.

## Consequences

- Upgrade, downgrade, rebuild and autogenerate drift checks are executable.
- No `create_all` or automatic startup migration path exists.
- The API and inert worker composition remain unchanged and side-effect free.
- TRD Bot projections, checkpoints, jobs, outbox, sessions, credentials,
  portfolios, journals, and exports remain deferred to their owning stages.
- The local Compose database is loopback-only and is not a production topology.
