# Nexora Web

The Web application is the private, bilingual, single-owner Nexora shell.

- `/fa` and `/en` open the authenticated workspace in RTL and LTR.
- `/{locale}/bootstrap` consumes a one-time bootstrap token and registers the
  first passkey.
- `/{locale}/login` authenticates with WebAuthn only.
- Browser API requests use only same-origin `/api` paths.
- Session identity remains in a Secure HttpOnly cookie; unsafe requests use the
  dedicated same-origin CSRF cookie.
- No identity token is persisted in browser storage.

## Interface styling

`src/app/globals.css` is the Tailwind entry for the Web application. Use
Tailwind utilities for new layouts and use `@apply` in the corresponding
file under `src/styles` when a reusable class needs the same composition.
Variants that use shared colors, spacing or radii draw on the design tokens
in `@nexora/ui/tokens.css`.

Shared components are implemented in individual modules under
`packages/ui/src/primitives` and exposed through `@nexora/ui/primitives`.
Shared style families live under `packages/ui/src/styles`. The app loads
these styles once through its Tailwind entry. Runtime values such as chart
colors and progress percentages use CSS custom properties consumed by
Tailwind utilities.
