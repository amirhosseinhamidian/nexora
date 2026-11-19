# NEX-P4-09 Exports and settings

The [Phase 4 roadmap](47-phase-four-product-experience-roadmap.md) assigns
this stage to exports and bounded owner preferences. The
[P4-08 Freeze](../../artifacts/p4-08/monitoring-experience-ui-freeze.json)
is present at `c10ecffd33a3b12bfce61b7f10da31a3719e6fea`.
[CI succeeded on that commit](https://github.com/amirhosseinhamidian/nexora/actions/runs/44484280599).

## Export workspace

The `/{locale}/exports` page lets an authenticated owner select an export
profile, one or more of JSON, CSV and Parquet, and the pinned retention class.
Confirmation shows the chosen profile, formats and retention setting.
The existing `POST /v1/portfolio-exports` operation creates a ZIP containing
the workspace's exportable portfolio and Decision Intelligence data.
`private_complete` includes allowed notes and source details. The
`ai_safe` profile removes free text and other sensitive fields defined by
the existing contract. Both produce private artifacts.

The browser keeps up to 20 receipt summaries per owner. Each receipt records
the artifact identity, version, profile, formats, time, size and fingerprints.
The existing API exposes publication and authenticated download. The history
covers receipts captured by this browser only. ZIP bytes and export datasets
stay out of browser history storage.

A verification request reads the bytes through the authenticated artifact
route. The client checks the server's SHA-256 header, the ZIP size and the
SHA-256 computed from the returned bytes against the publication receipt.
A download repeats these checks before offering the file to the browser.
The page shows unavailable and integrity-error states from that attempt.

## Settings workspace

The `/{locale}/settings` page supports Persian and English, system/light/dark
theme, a bounded display time zone and desktop sidebar state. Language and
theme are browser preferences available before sign-in. Time zone and sidebar
state are stored per owner in the browser. The time zone changes how the
workspace displays timestamps. Date and time inputs continue to use the device
clock. Monitoring settings link to the existing watchlists page. Provider
status uses the existing owner Decision feed and is read-only.

## Acceptance

```bash
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e

.venv/bin/python scripts/verify_exports_settings_ui.py
.venv/bin/python -m unittest discover -s tests -v
```

The [exports and settings workflow](https://github.com/amirhosseinhamidian/nexora/actions/runs/44487892642)
passed its contract and Chromium jobs on candidate
`fadb47a482c6ee2b39c12ef94adff19eb061e4ad`. The checksummed
[Freeze record](../../artifacts/p4-09/exports-settings-ui-freeze.json)
binds that run to the [candidate contract](../../contracts/nexora-v0.1-exports-settings-ui.json)
and opens `NEX-P4-10` for content, localization, accessibility and responsive hardening.
