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
bound. P1-13 accepts either exact loopback `127.0.0.1` for a same-host,
remote-disabled installation or an authenticated private-overlay address when
remote access is required. LAN-only, wildcard and public binds are forbidden.
PostgreSQL, API, web and worker ports remain internal. TLS, database and
identity secrets are mounted from operator-owned read-only files; Compose does
not create, migrate, or print them. Run migrations as an explicit release step
before starting this topology.

API and Worker write structured JSON logs to the private `nexora-logs` volume.
The volume is not exposed by ingress. Application handlers enforce bounded
rotation; 30-day retention and archival execution remain an operations task for
NEX-P1-12.

The API mounts the dedicated `nexora-artifacts` volume at
`/var/lib/nexora/artifacts`. Neither ingress nor Web mounts this volume, and it
is not a public static directory. P1-10 enforces immutable manifests, checksums,
quota and retention dry-runs inside the adapter; encrypted backup and retention
execution remain NEX-P1-12 responsibilities.
