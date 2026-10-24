# ADR 0012: Bounded local artifact storage and retention

Status: **Accepted candidate for NEX-P0-04**

## Context

Nexora v0.1 is a private single-host system. Introducing S3-compatible object
storage before multi-host operation would add credentials, network dependencies,
and failure modes. Conversely, an unbounded local directory would eventually
consume the host disk and make evidence, exports, and backups unreliable.

## Decision

Production artifacts use the existing `versioned_local_filesystem_adapter` on a
dedicated encrypted host volume. Published artifacts are immutable, addressed by
owner/type/ID/version, protected by SHA-256 manifests, and made visible only
after write, fsync, and atomic rename. Downloads pass through the authenticated
API; no directory or bucket is public.

The reference capacity is a 4-core, 8-GiB host with 200 GiB encrypted storage.
The artifact soft limit is 100 GiB and at least 20% disk space remains free.
Alerts trigger at 70%, 85%, and 95%. At the final threshold, non-critical
artifact writes enter write protection before immutable evidence is discarded.

Retention runs daily, idempotently, with dry-run and audit evidence. Immutable
source and financial records have no automatic deletion in v0.1. Temporary
exports, logs, metrics, jobs, outbox rows, sessions, and challenges have explicit
retention windows. S3-compatible storage remains deferred until a multi-host or
capacity trigger is approved.

## Consequences

- The initial deployment has no object-store service or cloud credential.
- Disk capacity and retention become release-tested operational controls.
- Off-host encrypted backups remain mandatory because local versioning is not a
  backup.
- Migration to S3-compatible storage must preserve manifests, checksums,
  immutability, and authenticated access.
