# ADR 0011: Secret and encrypted-backup boundary

Status: **Accepted and frozen by NEX-P0-04**

## Context

Nexora stores sensitive personal financial evidence. Source control, container
images, logs, exports, and ordinary database rows are inappropriate secret
distribution mechanisms. Export artifacts are portable analytical evidence,
not complete operational backups.

## Decision

Production secrets are injected as read-only mounted files with owner-only
permissions. Local development may use an untracked environment file. Secrets
are forbidden in Git, images, logs, browser bundles, database records, and every
export profile. CI performs secret scanning and the runtime later applies
structured redaction.

Database and artifact backups are encrypted for an offline age X25519 recipient
and include SHA-256 manifests. The recipient private key is never stored on the
runtime host. Restore requires owner presence and recent reauthentication, then
revokes all sessions and rotates service tokens. A successful restore drill is
required before release acceptance.

## Consequences

- Losing the offline recipient key makes encrypted backups unrecoverable.
- Restoring files alone is not sufficient; rotation and verification steps are
  part of recovery.
- AI-safe and private exports remain deliberately unable to recreate secrets or
  sessions.
