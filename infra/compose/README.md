# Private Compose runtime

`postgresql.dev.yml` provides only the loopback-bound PostgreSQL 17 development
database required to exercise Nexora migrations and durable-work integration
tests. It is not a production
topology and it does not expose PostgreSQL beyond `127.0.0.1`.

The password must come from an absolute private file outside the repository:

```bash
export NEXORA_DEV_DB_PASSWORD_FILE=/absolute/path/to/nexora-postgresql-password
docker compose -f infra/compose/postgresql.dev.yml up -d
```

The production-like private single-host topology remains deferred until the
runtime services and identity boundary exist.
