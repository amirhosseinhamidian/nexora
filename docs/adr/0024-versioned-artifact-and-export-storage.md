# ADR 0024 — Versioned artifact and export storage

Status: Candidate for NEX-P1-10
Date: 2026-10-27

## Decision

Nexora stores source artifacts, verified export bundles and future backup
artifacts behind an `ArtifactStorage` interface. The v0.1 implementation is a
versioned local-filesystem adapter rooted on a dedicated private volume. Every
identity component is validated before it becomes a path segment, and every
artifact remains scoped by owner, namespace, type, artifact ID and version.

Publication writes content and a canonical manifest into a same-parent staging
directory, fsyncs both files and the directory, then atomically renames the
whole version into visibility and fsyncs its parent. Published content is
immutable, mode `0440`, and verified against its SHA-256 and byte length on
read. An identical retry is idempotent; a conflicting retry fails closed.

Complete TRD Bot exports are stored as deterministic ZIP bundles containing the
frozen `nexora-export-manifest-v1` plus exactly the files declared by that
manifest. Missing, unexpected, path-traversing, size-mismatched or
checksum-mismatched files are rejected before publication.

## Capacity and retention

The soft quota is 100 GiB, the hard quota is 160 GiB and 20% filesystem free
space is reserved. Usage states change at 70%, 85% and 95% of the soft quota.
At the final threshold non-critical writes stop; the hard limit and free-space
reserve stop every write.

P1-10 only produces an idempotent retention dry-run. It may select unpinned
exports older than 30 days, but it never deletes source evidence, financial
records, pinned exports or backups. Retention execution, encrypted backup and
restore remain owned by NEX-P1-12.

## Consequences

- No public directory, public bucket or browser filesystem access exists.
- The adapter is registered in private API composition on the dedicated
  `nexora-artifacts` volume.
- The authenticated download route is deliberately deferred to NEX-P1-11.
- S3-compatible storage remains an interface-compatible future adapter and no
  cloud credential is introduced.
