# NEX-P4-02 — Platform Shell, Navigation and Routes

Status: **Frozen at candidate `cd3dd588c830707860fa872e09f1ec122cc4eb03`**

The local workspace now opens on Overview and uses stable, locale-prefixed
paths. A shared layout keeps navigation, language and appearance controls,
session recovery and sign-out available across workspace pages. Login and
Bootstrap use their own pages outside the workspace layout.

| Path after the locale        | Available in P4-02                                                                            |
| ---------------------------- | --------------------------------------------------------------------------------------------- |
| `/overview`                  | Existing read-only portfolio dashboard and accounts                                           |
| `/portfolios`                | Existing portfolio selector with a link to the selected portfolio                             |
| `/portfolios/{portfolio_id}` | Direct access to the selected owner's portfolio and accounts                                  |
| `/transactions`              | Existing transaction journal, holdings, imports and reconciliation for the selected portfolio |
| `/decisions`                 | Existing decision workflow with its connected journal, alerts and watchlists                  |
| `/alerts`                    | Existing alert inbox and watchlists                                                           |
| `/journal`                   | Existing outcome journal with lookup by decision identifier                                   |
| `/exports` and `/settings`   | Dedicated paths with a description of what is available                                       |

A missing portfolio identifier shows a link back to the list. Detail requests
are sent only for portfolios returned by the existing owner-scoped registry.
Sensitive transaction operations continue to use the session's recent
reauthentication flag.

On desktop the sidebar begins at the reading edge: right for Persian and left
for English. The icon-only collapsed view keeps accessible link names. On
mobile the shared drawer closes on link navigation or Escape, confines keyboard
focus and restores focus on dismissal. Pages use a full-width frame with
responsive padding and a standard main heading.

The onboarding wizard is assigned to P4-03, registry management to P4-04, and
export and settings workflows to P4-09. The existing backend and private
deployment contracts continue to define those capabilities and their gates.

The prerequisite is the [P4-01 Freeze](../../artifacts/p4-01/ui-foundation-freeze.json)
verified by [GitHub Actions](https://github.com/amirhosseinhamidian/nexora/actions/runs/44319372484).
The candidate passed local verification and the
[platform shell workflow](https://github.com/amirhosseinhamidian/nexora/actions/runs/44322665757)
on the same commit. The checksummed
[Freeze record](../../artifacts/p4-02/platform-shell-freeze.json) opens
`NEX-P4-03` for first-run onboarding and first portfolio creation.
