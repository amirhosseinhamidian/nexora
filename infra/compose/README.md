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

`private-single-host.yml` is the P1-06 production topology: only HTTPS 443 is
bound, and the bind address must be the authenticated private-overlay address.
PostgreSQL, API, web and worker ports remain internal. TLS, database and
identity secrets are mounted from operator-owned read-only files; Compose does
not create, migrate, or print them. Run migrations as an explicit release step
before starting this topology.
