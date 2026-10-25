# ADR 0018: Fail-closed versioned TRD Bot adapter

- Status: Candidate for NEX-P1-04
- Date: 2026-10-25

## Context

Nexora must consume TRD Bot evidence without sharing its database, importing
exchange credentials, or silently assuming compatibility. The frozen P0-03
boundary defines eight HTTP operations, typed envelopes, an explicit release
matrix and at-least-once delivery semantics. TRD Bot 0.3.0 does not implement
that boundary and therefore cannot be treated as a compatible provider.

## Decision

Nexora provides a synchronous, typed HTTP adapter under
`nexora.adapters.trd_bot`. Every data operation is blocked until capabilities
have been negotiated. Compatibility is limited to TRD Bot `>=0.3.1,<0.4.0`
with an exact match for contract, event, export, source-reference and command
capabilities. Missing fields, unknown schemas, response-header drift and a
provider version change fail closed.

The base URL and bearer token are read from separate absolute private files.
Production requires HTTPS and mode `0400`; development permits owner-only files
and loopback HTTP. Redirects are disabled. The token is never part of a model
dump, log, browser response or committed fixture.

Safe requests and idempotent POST operations retry only status 429, 502, 503 or
504, for at most four attempts, using bounded full jitter and `Retry-After`.
Status 410 becomes an explicit full-snapshot-resync signal. Status 412 clears
the negotiated state so another operation cannot run until renegotiation.

## Consequences

- All eight frozen integration operations have typed request/response models.
- Tests use `httpx.MockTransport`; this stage makes no claim about a live TRD
  Bot 0.3.1 deployment.
- The adapter is not registered in API or Worker composition in P1-04, so
  importing or starting Nexora creates no external connection.
- Durable scheduling, checkpointing, projection persistence, lease/reclaim and
  transactional outbox remain owned by NEX-P1-05.
- Direct TRD Bot database access, live orders, exchange credentials and wallet
  capabilities remain forbidden.
