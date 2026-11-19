# NEX-P4-10 Content, accessibility and responsive hardening

The [Phase 4 roadmap](47-phase-four-product-experience-roadmap.md) assigns
this stage to copy, localization, keyboard access and responsive behavior.
The [P4-09 Freeze](../../artifacts/p4-09/exports-settings-ui-freeze.json)
is present at `86c013131de77e036e0a8b81c98ea8a2644b6891`.
[CI succeeded on that commit](https://github.com/amirhosseinhamidian/nexora/actions/runs/44490292631).

## Copy review

| Pages | Reviewed content |
| --- | --- |
| Sign-in, first-time setup and route fallbacks | Device approval, setup code, session recovery and loading and error messages |
| First portfolio setup and registries | Setup steps, section names, field hints, lifecycle labels and error recovery |
| Overview and portfolio details | Portfolio, account, valuation and chart labels |
| Accounting pages | Transaction journal, holdings, import publication and reconciliation language |
| Decision and Candidate pages | Evidence, risk, simulated portfolio impact, scenarios and human reviews |
| Alerts, watchlists and outcome journal | Alert state and actions, monitoring preferences and outcome entries |
| Exports and settings | Private export profile, file verification, display preferences and source status |

Persian uses «کلید عبور» for passkey, «پرتفوی» for portfolio, «دفتر تراکنش»
for the accounting journal, and «دفتر نتایج» for the outcome journal. The
Persian and English dictionaries have the same message inventory. File
formats, source names, identifiers and checksums preserve their written
values. Changing language keeps the active record and filters in the address.

## Interaction and layout

- The skip link is available on sign-in and setup pages. Workspace route
  navigation moves focus to the main region.
- An open dialog keeps focus inside and marks its background inert. Closing
  it restores keyboard focus to its opener.
- Shared form fields associate descriptions and errors with their controls.
  Scrollable tables use their caption or explicit label to name their region.
- Focus, field boundaries and status text use shared light and dark color
  tokens. The verifier checks selected text pairs against 4.5:1 and focus
  and control pairs against 3:1. See the WCAG 2.2 criteria for
  [text contrast](https://www.w3.org/TR/WCAG22/#contrast-minimum) and
  [non-text contrast](https://www.w3.org/TR/WCAG22/#non-text-contrast).
- Touch targets, narrow forms and dialogs use the available viewport.
  Long identifiers wrap, and wide tables scroll inside their own region.
  Tooltips follow the current writing direction, and the system's
  reduced-motion preference suppresses interface motion.

## Acceptance

The Chromium matrix exercises Persian and English routes at 320, 768,
1280 and 1920 pixels, with light and dark profiles across those sizes.
It checks document direction, theme, heading visibility and viewport overflow.
Separate scenarios cover keyboard dismissal and focus restoration, the
language switch and local feedback. Manual visual acceptance is part of P4-11.

```bash
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e

.venv/bin/python scripts/verify_experience_hardening_ui.py
.venv/bin/python -m unittest discover -s tests -v
```

## Freeze

`NEX-P4-10` is frozen at candidate `721a6af24043bb85cfe0fe148d53856d4adafbe6`.
The contract and Chromium jobs passed on that commit in
[GitHub Actions run 44496297500](https://github.com/amirhosseinhamidian/nexora/actions/runs/44496297500).
The [Freeze record](../../artifacts/p4-10/experience-hardening-ui-freeze.json)
binds those jobs to the [candidate contract](../../contracts/nexora-v0.1-experience-hardening-ui.json)
and opens `NEX-P4-11` for end-to-end product acceptance.
