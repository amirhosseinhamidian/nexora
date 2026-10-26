# Nexora server

The server package contains a minimal FastAPI liveness boundary, a fail-closed worker,
typed non-secret runtime settings, one explicit composition factory shared by
both entry points, and an unregistered PostgreSQL persistence adapter used by
explicit Alembic operations. It also contains an unregistered, typed TRD Bot
client adapter whose network behavior is exercised only through mock transports
in P1-04. P1-05 adds PostgreSQL durable jobs, checkpoints, a transactional
outbox, and a generic explicit-handler worker engine. P1-08 adds bounded JSON
logging, recursive secret redaction, route-template request metrics, worker and
database-pool metrics, and dependency-aware readiness. Scheduled provider
synchronization and production readiness are intentionally deferred.

```bash
uv run nexora-api
uv run nexora-worker --check
```

Configuration is read only from the allowlisted `NEXORA_*` process environment
variables documented in `.env.example`. Unknown prefixed variables and unsafe
profile combinations fail closed; dotenv files are never loaded automatically.

`NEXORA_LOG_FILE` is optional during local development and required in the
private production profile. Production writes UTF-8 JSON Lines to an absolute,
non-symlink path with 10 MiB size rotation and 30 backups. Request query/body,
raw exception messages and authentication material are never valid log fields.

Database migrations use a separate operator-only configuration path. Set
`NEXORA_MIGRATION_DATABASE_DSN_FILE` to an absolute private file containing one
`postgresql+psycopg` DSN, then invoke Alembic explicitly. Application startup
does not connect to PostgreSQL or mutate schema at application startup.

The TRD Bot adapter reads its base URL and bearer token from absolute private
files named by `NEXORA_TRD_BOT_BASE_URL_FILE` and
`NEXORA_TRD_BOT_TOKEN_FILE`. These adapter-only settings are not part of the
runtime composition allowlist yet, so API and Worker startup remain side-effect
free. A caller must explicitly load the files, construct the adapter and
negotiate exact v1 capabilities before any data operation.

The worker only claims job types present in an injected handler registry. The
default CLI has no provider handlers and therefore refuses to claim work; its
`--check` mode remains side-effect free. Durable delivery is at-least-once, so
handlers and downstream consumers must honor the owner-scoped idempotency keys.
