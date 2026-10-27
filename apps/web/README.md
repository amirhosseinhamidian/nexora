# Nexora Web

The Web application is the private, bilingual, single-owner Nexora shell.

- `/fa` and `/en` render the authenticated workspace in RTL and LTR.
- `/{locale}/bootstrap` consumes a one-time bootstrap token and registers the
  first passkey.
- `/{locale}/login` authenticates with WebAuthn only.
- Browser API requests use only same-origin `/api` paths.
- Session identity remains in a Secure HttpOnly cookie; unsafe requests use the
  dedicated same-origin CSRF cookie.
- No identity token is persisted in browser storage.

Portfolio-domain navigation remains disabled until Phase 2.
