# NEX-P1-10 — Artifact and Export Storage

This stage closes `NEX-P1-GAP-006` with the private, owner-scoped persistence
boundary required by future exports and authenticated downloads.

## Delivered boundary

- `ArtifactStorage` protocol and `versioned_local_filesystem_adapter`;
- owner/namespace/type/artifact/version path isolation;
- separate `source`, `export` and `backup` namespaces;
- canonical `nexora-artifact-manifest-v1` metadata;
- SHA-256 and byte-length verification on every read;
- same-parent staging, file and directory fsync, atomic rename and parent fsync;
- immutable file modes and conflict-safe idempotent retry;
- deterministic complete ZIP bundles for frozen TRD Bot export manifests;
- traversal, symlink, partial-export and checksum negative tests;
- 100 GiB soft quota, 160 GiB hard quota and 20% free-space reserve;
- 70/85/95 percent storage states and non-critical write protection;
- idempotent 30-day unpinned-export retention dry-run;
- reconciliation for corrupt manifests, orphan content and abandoned staging;
- a dedicated non-public private Compose volume.

`NEXORA_ARTIFACT_ROOT` must be an absolute path. In the private single-host
topology it resolves to `/var/lib/nexora/artifacts`, backed by the
`nexora-artifacts` volume. It is never mounted into the Web container or served
as static content.

## Export boundary

The publisher accepts only a validated `nexora-export-manifest-v1` and the exact
set of bytes declared by it. Each path, size and SHA-256 is checked before the
bundle is published. The bundle keeps the source manifest alongside files in a
stable order with deterministic ZIP metadata, making identical retries produce
the same artifact identity.

P1-10 stores verified output but does not create financial projections, expose
an unauthenticated download URL or claim that TRD Bot 0.3.0 can produce the
frozen export contract.

## Deferred

- authenticated download API and browser flow (`NEX-P1-11`);
- retention execution, encrypted backup and restore (`NEX-P1-12`);
- final capacity and overload acceptance (`NEX-P1-13`);
- S3-compatible adapter, SaaS, multi-user, AI/ML and live trading.

## Freeze evidence

Candidate `707795735e156ebbd973f08709e52c5a994e2d17` with commit message
`feat(nexora): implement P1-10 artifact and export storage` passed the primary
[Artifact and export storage workflow](https://github.com/amirhosseinhamidian/nexora/actions/runs/40524390732)
and all eleven regression workflows on the same SHA. The evidence records the
contract, backend, atomic publication, deterministic export, private topology,
cross-language, PostgreSQL 17 and Web regression gates.

`NEX-P1-10` is therefore frozen. The next allowed stage is `NEX-P1-11`, which
owns the authenticated Web application shell and download flow. This freeze
does not enable public artifact access, retention deletion, cloud credentials,
live trading, wallets or autonomous AI execution.
