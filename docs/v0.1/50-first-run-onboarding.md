# NEX-P4-03 — First-run onboarding

Status: **Frozen at candidate `7f48919ff2940d9634477d71d6d2ab68f910c83e`**

The private workspace offers an onboarding link when the owner has no
registered portfolios. In the guide, the owner chooses an active base asset
or registers a new one, names the first portfolio, and optionally adds an
account for record keeping. The review and confirmation precede the first
write. The completed page links to the new portfolio.

## Recovery

The guide uses the existing owner-scoped registry and the shared same-origin
API client. Each successful write remains available if a later request fails.
The guide checks registry keys and submitted fields before reusing a record
and uses the same keys when retrying. A per-tab, owner-scoped draft preserves
the form and confirmed progress across a reload or a return from passkey login.
If browser storage is blocked, the guide can retain the form while it stays
open. An owner who already has a portfolio is directed to the portfolio list
unless a matching setup draft is still in progress.

The three registry writes are independent. A later failure can leave an asset
or portfolio already saved. The guide preserves that progress and uses the
existing registry constraints to prevent a retry from creating another copy.

The prerequisite is the [P4-02 Freeze](../../artifacts/p4-02/platform-shell-freeze.json)
verified by [GitHub Actions](https://github.com/amirhosseinhamidian/nexora/actions/runs/44324072191).
The accepted candidate includes the onboarding implementation and its
formatting fix. The [onboarding workflow](https://github.com/amirhosseinhamidian/nexora/actions/runs/44387482135)
passed its contract and web jobs on that commit, including Chromium coverage.
The checksummed [Freeze record](../../artifacts/p4-03/first-run-onboarding-freeze.json)
opens `NEX-P4-04` for asset, portfolio and account management.
