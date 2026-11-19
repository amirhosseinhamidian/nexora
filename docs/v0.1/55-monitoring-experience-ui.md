# NEX-P4-08 Alerts, watchlists and outcome journal

The [Phase 4 roadmap](47-phase-four-product-experience-roadmap.md) assigns this
stage to the routed monitoring workflow. The
[P4-07 Freeze](../../artifacts/p4-07/decision-intelligence-ui-freeze.json) is
present at `567fdc1f12b64ce5549e692a0c1082f1c5afe00f`.
[CI succeeded on that commit](https://github.com/amirhosseinhamidian/nexora/actions/runs/44478313009).

## Pages

| Path | Purpose |
| --- | --- |
| `/{locale}/alerts` | Browse owner alerts, filter by Decision or saved watchlist preferences, or open one alert |
| `/{locale}/alerts/watchlists` | Create watchlists, add references and save display preferences |
| `/{locale}/journal` | Load a Decision's outcome journal and append entries or corrections |

An alert link uses `?alert=` to open its details. The `?decision=` filter
matches an explicit Decision identifier in the source alert. Alert details
link to the corresponding Decision and outcome journal when the source supplies
an unambiguous `evaluation_id` or `decision_id`. Decision and Candidate pages
offer the reverse links when a Decision is available.

Open `?watchlist=` to use an existing watchlist's preferences on the alerts
returned by the owner inbox. The threshold uses severity values supplied by
the source, the sort uses the source observation time, and resolved-alert
visibility follows the saved preference. Watchlist items organize references.
The inbox filter uses display preferences only.

## Saved changes

Acknowledging or snoozing shows a confirmation for the specific alert. The
snooze time must be in the future. The request includes the expected state
version and exact source evidence identifiers. The detail view shows the
recorded transition history and scheduled resume time.

Watchlist item and preference updates use the aggregate version. Conflicts
refresh the record for another review. The journal opens directly with
`?decision=` and keeps the Decision visible during confirmation. A correction
adds a new entry linked to its original. The original content stays visible.
Observed outcomes preserve the required source lineage.

A retry after an uncertain response uses the original idempotency key and
payload. The UI uses the existing owner-scoped API operations. Alert and
watchlist preferences affect local presentation, and external notifications
and provider subscriptions stay disabled.

## Acceptance

```bash
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e

.venv/bin/python scripts/verify_monitoring_experience_ui.py
.venv/bin/python -m unittest discover -s tests -v
```

The [candidate contract](../../contracts/nexora-v0.1-monitoring-experience-ui.json)
requires CI on the candidate commit before `NEX-P4-08-FREEZE`. The Freeze
opens `NEX-P4-09` for Exports and Settings.
