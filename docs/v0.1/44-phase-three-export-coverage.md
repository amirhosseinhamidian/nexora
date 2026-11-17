# NEX-P3-11 — Phase 3 Export Coverage

Status: **Candidate — requires same-SHA CI acceptance**

P3-11 extends the existing authenticated Portfolio export so the complete
Decision Intelligence history can be reviewed without introducing another
storage system or a public download surface.

## Coverage

Both `private_complete` and `ai_safe` include logical datasets for Decision
records, source references, human reviews, Portfolio impacts, Alert state
history, watchlists and the Outcome Journal. Lineage and uncertainty summaries
remain part of the manifest-backed snapshot.

Each Phase 3 logical dataset receives a deterministic SHA-256 digest in the
snapshot lineage. Provider source checksums, review and Alert evidence
checksums, and Journal lineage checksums remain present in their records. The
existing snapshot, file and ZIP bundle checksums continue to protect the whole
export.

## Profiles

`private_complete` contains every allowed owner-scoped Phase 3 field.
`ai_safe` preserves structural evidence, source lineage and uncertainty while
removing owner free text, raw provider payloads, provider delivery identifiers,
idempotency material and other previously frozen sensitive categories. Security
and identity tables remain outside both profiles.

## Snapshot and delivery boundary

The PostgreSQL source is captured with repeatable-read isolation and bounded
record counts. Export generation remains deterministic and fail-closed; a
partial artifact is never published. The existing `/v1/portfolio-exports`
operation and authenticated owner-scoped artifact download path are reused.
There is no public URL, public bucket, owner override, new table or migration.

## Transition

P3-11 is accepted only when its dedicated workflow and regression gates pass
on the implementation SHA. Successful CI acceptance opens `NEX-P3-12`; Phase 3
acceptance, accessibility E2E and production readiness remain deferred.
