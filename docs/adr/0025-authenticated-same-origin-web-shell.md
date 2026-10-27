# ADR 0025: Authenticated same-origin Web shell

- Status: Candidate for NEX-P1-11
- Date: 2026-10-27

## Decision

Nexora serves its bilingual private Web experience through the reverse proxy and
uses only the same-origin `/api` boundary. Caddy strips that prefix before
forwarding requests to the FastAPI runtime. The browser never receives the
opaque session token: it remains in the Secure, HttpOnly,
`SameSite=Strict` `__Host-nexora_session` cookie.

Unsafe requests remain protected after a page reload by a separate Secure,
`SameSite=Strict` `__Host-nexora_csrf` cookie. It is intentionally readable by
the same-origin Web client and contains only the CSRF token. Session and CSRF
material are never persisted in `localStorage` or `sessionStorage`.

Every HTML response receives a runtime CSP nonce. The nonce is forwarded to the
theme bootstrap script; production policy permits neither `unsafe-inline` nor
`unsafe-eval`. Persian is RTL with Vazirmatn Variable and English is LTR with
Inter Variable.

The artifact adapter is exposed only through an authenticated, owner-scoped
download route fixed to the `export` namespace. The route verifies manifest
identity, length and SHA-256 before returning an attachment. Source evidence and
backup namespaces cannot be downloaded through this boundary.

## Consequences

- Passkey bootstrap and login are the only human identity flows.
- The shell explicitly represents loading, offline, error, empty and expired
  session states.
- Deferred Portfolio pages appear only as disabled navigation; no domain data is
  fabricated in Phase 1.
- Browser E2E tests cover locale direction, passkey-only login and expiry.
- Private deployment hardening and operational acceptance remain in P1-12 and
  P1-13.
