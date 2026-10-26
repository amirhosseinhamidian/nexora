# ADR 0020: Passkey, opaque session and private runtime implementation

Status: **Candidate for NEX-P1-06**

## Context

P0-04 froze a passkey-first, single-owner identity and a private-only production
topology. P1-03 and P1-05 delivered the PostgreSQL and durable-work foundations,
but identity state and security audit evidence were not yet runtime capabilities.

## Decision

Nexora uses the pinned `webauthn` 2.7.0 verifier with required user verification,
exact RP origin/ID matching, and only ES256 or EdDSA. Challenge, bootstrap,
recovery, session and service-token records persist digests or public material;
raw authenticators, session tokens, recovery codes and service tokens never enter
the database. An unconfigured ceremony verifier denies every ceremony.

Opaque sessions use a host-only Secure/HttpOnly/SameSite=Strict cookie, 30-minute
idle and 12-hour absolute expiry, 15-minute rotation, 30-second rotation grace,
and a maximum of five concurrent sessions. Recovery consumes one digest,
revokes every session and passkey, and forces a new registration ceremony.

Production composition requires operator-mounted database, canonical-origin and
authentication-pepper files. The Compose topology publishes only TLS port 443
on an explicitly supplied private-overlay address; database and worker ports are
not published. Migrations remain a separate release operation.

## Consequences

- The owner has no password, email reset, registration or invitation surface.
- Security events are append-only and never contain raw credentials.
- WebAuthn verification depends on a pinned audited library rather than custom
  cryptography.
- The topology is private single-host and is not a public-internet or SaaS
  deployment claim.
- Phase 1 still requires its acceptance/freeze evidence before production use is
  claimed.
