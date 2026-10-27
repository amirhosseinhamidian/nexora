# NEX-P1-11 — Authenticated Web Application Shell

This candidate closes `NEX-P1-GAP-007` and turns the design foundation into a
real private, single-owner application entry point.

## Delivered

- Persian RTL and English LTR bootstrap, login and authenticated-shell routes;
- local Vazirmatn Variable and self-hosted Inter Variable typography;
- dark, light and system themes without storing identity material;
- WebAuthn passkey bootstrap and login with no password or self-registration;
- Secure, HttpOnly session cookie plus a dedicated Secure CSRF cookie;
- a fail-closed same-origin `/api` client and Caddy prefix stripping;
- loading, empty, offline, error and session-expired states;
- responsive desktop/mobile navigation and accessibility landmarks;
- runtime-nonce CSP and authenticated `no-store` responses;
- authenticated, owner-scoped, integrity-checked export downloads;
- Vitest and Playwright coverage for the critical shell lifecycle.

The Portfolio, Analytics, Decisions, Alerts and Reports destinations remain
visibly disabled. Their domain behavior belongs to Phase 2; P1-11 does not
invent holdings, balances or trading activity.

## Security boundary

The opaque session token is available only to the server through
`__Host-nexora_session`. The same-origin client reads only
`__Host-nexora_csrf`, supplies it for unsafe requests and stores neither token
in browser storage. The API client rejects absolute, protocol-relative and
non-`/api` targets.

Exports are never mounted into the Web container or served statically. An
authenticated owner may download only an artifact in their own `export`
namespace; missing or invalid identities return 404 and integrity failures fail
closed.

## Verification

Run:

```bash
uv run python scripts/verify_authenticated_web_shell.py
uv run python -m unittest tests.test_authenticated_web_shell -v
uv run pytest apps/server/tests/test_runtime_api.py -q
pnpm --filter @nexora/web format:check
pnpm --filter @nexora/web lint
pnpm --filter @nexora/web typecheck
pnpm --filter @nexora/web test
pnpm --filter @nexora/web build
pnpm --filter @nexora/web test:e2e
```

The Playwright command requires the Chromium runtime and a host that permits the
Next.js development server to enumerate network interfaces.

## Deferred

- private deployment, backup/restore, retention execution and overload drills
  (`NEX-P1-12`);
- final Phase 1 acceptance and freeze (`NEX-P1-13`);
- Portfolio domain features (Phase 2);
- SaaS, multi-user, public deployment, AI/ML and live trading.

The only next stage opened by this candidate is `NEX-P1-11-FREEZE`. After that
freeze, the next delivery stage is `NEX-P1-12`.
