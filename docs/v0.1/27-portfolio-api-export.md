# NEX-P2-09 — Portfolio API and deterministic export

Status: candidate

Decision date: 2026-11-02

Prerequisite: frozen NEX-P2-08 at `37866ad1f3635bcbdeb7569366140e21b23485bc`

## Outcome

NEX-P2-09 exposes the frozen Paper/Shadow projection through an authenticated, owner-scoped read operation and adds bounded portfolio export publication. Exports are immutable private artifacts; the API returns only the existing authenticated artifact download path. It never creates a public URL or public bucket object.

The implementation adds no mutable database table and no migration. It reads the existing owner-scoped portfolio, journal, reconciliation, holdings, valuation, analytics, performance, and Paper/Shadow projection data.

## HTTP boundary

| Method and path | Purpose | Boundary |
| --- | --- | --- |
| `GET /v1/trd-bot/paper-shadow-projection` | Rebuild and return the current frozen projection | Authenticated session; owner comes only from the session |
| `POST /v1/portfolio-exports` | Capture and publish one complete export | Authenticated session, exact origin, CSRF, strict JSON body |
| `GET /v1/exports/{artifact_type}/{artifact_id}/versions/{version}/download` | Download the immutable ZIP | Existing authenticated, owner-scoped artifact route |

The export request accepts `profile`, one to three unique `formats`, and `pinned`. Supported profiles are `private_complete` and `ai_safe`; supported content formats are JSON, CSV, and Parquet. The delivery object is always a manifest-backed ZIP.

## Snapshot and determinism

The PostgreSQL source captures financial tables with repeatable-read semantics, owner filters, primary-key ordering, and an explicit table allowlist. Derived NAV/P&L analytics, a bounded 31-point performance series, and the Paper/Shadow projection are included with lineage and uncertainty summaries.

Determinism is enforced by:

- canonical sorted-key JSON with exact decimal strings and no binary floats;
- stable dataset and record ordering;
- a fixed CSV schema containing dataset, record index, record checksum, and canonical record JSON;
- real Apache Parquet with the same lossless record envelope;
- fixed ZIP entry timestamps, permissions, compression, and lexical entry ordering;
- snapshot, per-file, bundle, and owner-scope checksums.

The manifest declares the schema versions, export identity, profile, timestamp, dataset counts, lineage, uncertainty, exclusions, file sizes/checksums, completeness, and `public_download: false`.

## Capacity and completeness

Synchronous export is bounded to 100,000 source records and 128 MiB of canonical uncompressed snapshot JSON. A request that exceeds either limit fails closed. No artifact is published until the entire snapshot and requested formats have been built, so a partial export cannot be observed or downloaded.

## Profile boundary

`private_complete` contains every field from the explicit portfolio-domain table allowlist except the session-derived `owner_id`. Both profiles exclude identity and security tables, including sessions, credentials, recovery codes, service tokens, WebAuthn state, and raw security audit context.

`ai_safe` additionally removes provider raw payloads/envelopes, external account references, idempotency/source references that can carry external identifiers, counterparties, memos, review reasons, and other free-text financial context. Every removed field is named in `excluded_fields` in the manifest. This is an export-safety boundary, not authorization for autonomous AI execution or model training.

## Verification

The P2-09 workflow verifies the frozen P2-08 evidence, the candidate contract checksum, runtime markers, strict API/session/CSRF behavior, deterministic JSON/CSV/Parquet/ZIP content, immutable artifact publication, owner isolation, AI-safe exclusions, PostgreSQL 17 integration, migration head stability, formatting, lint, typing, and the complete non-integration suite.

The only next stage before dashboard work is `NEX-P2-09-FREEZE`. After that freeze, `NEX-P2-10` may begin.
