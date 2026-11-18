# NEX-P4-05 — Portfolio overview and analytics

Status: **Candidate**

The [P4-04 Freeze](../../artifacts/p4-04/registry-management-ui-freeze.json)
passed [its workflow](https://github.com/amirhosseinhamidian/nexora/actions/runs/44395721270)
on commit `ea7025148103004a6441377077b14aee1014f328`.

Overview lets the owner select a portfolio. The portfolio detail route
opens the same dashboard for that specific portfolio. The dashboard shows net
asset value, realized and unrealized profit or loss, active accounts, and
valuation health. When net asset value is incomplete, it shows the value of
priced holdings separately. Allocation compares holdings with positive market
values and includes a table with the shares.

The holdings table uses the positions returned by the analytics snapshot, so
quantities and valuations refer to the same time. It shows the account,
quantity, market value, valuation date, and cost basis status. Quantities keep
the precision returned by the API. The valuation report counts assets, while
the holdings table shows the evidence for each position. The allocation and
holdings tables support keyboard and screen reader use and scroll within the
page on small screens.

The performance panel compares net asset values at the start and end of a
7-, 30-, or 90-day window ending at the snapshot time. It displays the
existing API's sampled cumulative return, which accounts for deposits
and withdrawals. Stale segments use a dashed line and missing values leave
gaps. The expandable data table lists the sampled dates, net asset values,
flows, returns, and the available reasons for gaps. Financial values remain
decimal strings until formatting, and conversion to numbers is used for
bounded chart coordinates.

The [P2-07 analytics contract](25-nav-pnl-performance.md) defines how the
read-only figures are calculated. P4-05 uses the existing owner-scoped
endpoints. Accounting workflows are assigned to P4-06.

After local verification and CI, the candidate opens `NEX-P4-05-FREEZE`.
