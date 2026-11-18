# NEX-P4-04 — Asset, portfolio and account management

Status: **Candidate**

The [P4-03 Freeze](../../artifacts/p4-03/first-run-onboarding-freeze.json)
passed [its workflow](https://github.com/amirhosseinhamidian/nexora/actions/runs/44389551521)
on commit `5742c742c2b713cd54590bffe0c630de01969dc7`.

## Owner workspace

| Localized route | Available actions |
| --- | --- |
| `/{locale}/assets` | Register assets, attach identifiers and deactivate active assets. |
| `/{locale}/portfolios` | Create portfolios with an active base asset, open historical records and archive active portfolios. An empty registry links to first-run onboarding. |
| `/{locale}/accounts` | Register accounts under an active portfolio, filter by portfolio and close active accounts. |

Each page lists both active and historical records and supports search and
status filters. A confirmation shows the record and the effect of each
lifecycle action. The request uses the row version shown when the owner
opened that confirmation. On a conflict or uncertain result, the list is
loaded again before another action is available.

Creation reuses the generated registry key when the same submission is retried
in the current view. After a lost response, it checks the full input against
the stored record before reporting success. Asset identifiers can be added
through the existing endpoint. That API provides no historic identifier list.
Account registration accepts an optional institution name and keeps account
connection details out of the form.

The [P2-02 registry contract](20-portfolio-asset-account-registry.md) still
defines the available operations. Renaming, general edits, deletion and
reactivation require separate contract decisions. Authenticated same-origin
requests continue to use the workspace session and CSRF controls.

The candidate opens `NEX-P4-04-FREEZE` after local verification and CI.
Portfolio overview and analytics are assigned to P4-05.
