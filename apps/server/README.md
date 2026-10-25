# Nexora server

The server package contains a minimal FastAPI liveness boundary, an inert worker,
typed non-secret runtime settings, one explicit composition factory shared by
both entry points, and an unregistered PostgreSQL persistence adapter used by
explicit Alembic operations. Authentication, TRD Bot runtime integration,
durable jobs, and production readiness are intentionally deferred.

```bash
uv run nexora-api
uv run nexora-worker --check
```

Configuration is read only from the allowlisted `NEXORA_*` process environment
variables documented in `.env.example`. Unknown prefixed variables and unsafe
profile combinations fail closed; dotenv files are never loaded automatically.

Database migrations use a separate operator-only configuration path. Set
`NEXORA_MIGRATION_DATABASE_DSN_FILE` to an absolute private file containing one
`postgresql+psycopg` DSN, then invoke Alembic explicitly. Application startup
does not connect to PostgreSQL or mutate schema in NEX-P1-03.
