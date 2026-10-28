# Nexora private operations runbook

This runbook is for the single-owner, private single-host profile only. The host
must use encrypted storage. In the default same-host mode, ingress binds only
`127.0.0.1:443` and remote access is disabled. An authenticated private-overlay
address may be used when remote access is intentionally required. PostgreSQL,
API, Web and Worker have no host ports. LAN-only, wildcard and public-internet
deployment are not supported.

## Prerequisites

- Docker Engine with Compose v2;
- a four-core, 8 GiB host with 200 GiB encrypted storage;
- absolute secret-file paths matching `secret-inventory.example.json`;
- secret files readable by the container UID and no broader than their listed mode;
- a mounted off-host or independently administered backup destination;
- an age X25519 public recipient on the host and its private identity kept offline;
- the deployed 40-character commit SHA in `SOURCE_COMMIT_SHA`.

For a local-only reference host set `NEXORA_PRIVATE_BIND_ADDRESS=127.0.0.1`.
This mode does not require Tailscale, WireGuard or another overlay client, but
it also provides no remote access.

TRD Bot `0.3.0` must remain disabled. The base Compose file therefore requires
no TRD Bot URL or token and the Worker idles without claiming synchronization
jobs. Do not create placeholder credentials. The compatible-provider override
is reserved for a negotiated `>=0.3.1,<0.4.0` provider.

Validate the rendered topology before starting it:

```sh
docker compose -f infra/compose/private-single-host.yml config --quiet
docker compose -f infra/compose/private-single-host.yml up -d --build --wait
```

Run Alembic migrations as a separate, explicit operator action before replacing
an existing API or Worker. Do not enable SQLAlchemy schema auto-creation.

## Encrypted backup

The operations image pins PostgreSQL 17.6, Python 3.13.16, uv 0.13.4 and age
1.1.1. It creates a PostgreSQL custom dump and deterministic artifact archive,
checksums both, encrypts the bundle before publication, then atomically writes
identical encrypted copies plus canonical manifests to the runtime and off-host
roots. Secrets are never included. Schedule this command at least daily:

```sh
docker compose -f infra/compose/private-single-host.yml \
  --profile operations run --rm operations \
  /app/infra/operations/create-backup.sh
```

The runtime-host copy does not satisfy the off-host requirement. Monitor both
destinations and verify manifests regularly with `nexora-operations
verify-backup`. The target RPO is 24 hours.

## Restore drill

Restoration is destructive and must be owner-attended. Stop ingress, Web, API
and Worker, leave PostgreSQL available, mount the offline identity only for the
one restore container, and require all confirmations:

```sh
docker compose -f infra/compose/private-single-host.yml stop ingress web api worker
docker compose -f infra/compose/private-single-host.yml --profile operations run --rm \
  -v /absolute/offline/age-identity.txt:/run/restore/age-identity.txt:ro \
  -e NEXORA_RESTORE_IDENTITY_FILE=/run/restore/age-identity.txt \
  -e NEXORA_RESTORE_OWNER_PRESENT=yes \
  -e NEXORA_RESTORE_RECENT_REAUTHENTICATION=yes \
  -e NEXORA_RUNTIME_STOPPED_CONFIRM=yes \
  -e NEXORA_RESTORE_BACKUP_ID=YYYYMMDDTHHMMSSZ-1234abcd \
  -e NEXORA_RESTORE_CONFIRM=RESTORE-YYYYMMDDTHHMMSSZ-1234abcd \
  operations /app/infra/operations/restore-backup.sh
```

After restore, remove the identity mount, rotate the scoped TRD Bot service
token on both systems, run migrations and smoke tests, and only then restart
the runtime. All browser sessions and stored service-token records are revoked
by the restore. The target RTO is four hours. P1-13 records the actual timed
backup/restore drill against its candidate SHA.

## Retention and capacity

Retention is a daily, idempotent operation. It always writes separate artifact
and backup plans before any deletion; dry-run is the default. Only expired
unpinned export artifacts and verified backup pairs outside the 14 daily,
8 weekly and 12 monthly tiers can be removed. Immutable evidence, pinned
artifacts and an unpaired backup inventory are protected fail-closed.

```sh
docker compose -f infra/compose/private-single-host.yml --profile operations run --rm \
  operations /app/infra/operations/run-retention.sh

docker compose -f infra/compose/private-single-host.yml --profile operations run --rm \
  -e NEXORA_RETENTION_OWNER_APPROVED=yes \
  operations /app/infra/operations/run-retention.sh --apply
```

Use `nexora-operations capacity --database-bytes N` for a machine-readable
capacity report. Investigate at 20 GiB database usage, 100 GiB artifact usage,
or below 20% filesystem free space. Interactive overload returns HTTP 429 with
`Retry-After`; durable work remains queued and immutable evidence is never
dropped.
