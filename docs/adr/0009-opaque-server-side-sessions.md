# ADR 0009: Opaque server-side sessions

Status: **Accepted and frozen by NEX-P0-04**

## Context

Authenticated access exposes personal financial, portfolio, export, and
security-management data. Browser-readable bearer tokens and self-contained
long-lived JWTs make revocation, recovery, and incident response harder.

## Decision

Nexora uses 256-bit opaque session tokens. Only a SHA-256 digest is stored
server-side. The browser receives an `__Host-nexora_session` cookie with Secure,
HttpOnly, SameSite=Strict and Path=/ attributes, without Domain. No session
credential is stored in localStorage, sessionStorage, IndexedDB, or JavaScript
memory as an application token.

Sessions expire after 30 minutes idle or 12 hours absolute, rotate every 15
minutes and after authentication or privilege changes, and support immediate
single-session and global revocation. Unsafe same-origin requests additionally
require a synchronizer CSRF token and exact Origin validation.

## Consequences

- Logout, credential recovery, and incident response can invalidate access
  immediately.
- The database becomes part of session availability and cleanup operations.
- Horizontal scaling, if added later, must preserve one authoritative session
  store rather than changing the browser contract.
