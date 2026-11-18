# NEX-P4-06 Accounting and reconciliation experience

The [Phase 4 roadmap](47-phase-four-product-experience-roadmap.md) opens this
stage after the [P4-05 Freeze](../../artifacts/p4-05/portfolio-analytics-ui-freeze.json).
The Freeze is present at `437a635077ef4d1e5d219f9b7cb1f42e3ce85618`, with
[successful CI for that commit](https://github.com/amirhosseinhamidian/nexora/actions/runs/44404355235).

## Workspace routes

| Route | Records shown |
| --- | --- |
| `/{locale}/transactions` | Selected portfolio’s transaction journal, exact entry lines, source and correction links |
| `/{locale}/transactions/holdings` | Selected portfolio’s quantities and cost basis, with the calculation’s journal fingerprint |
| `/{locale}/transactions/lots` | Selected portfolio’s open purchase lots, acquisition dates, remaining quantities and cost basis |
| `/{locale}/transactions/imports` | Import previews and publication history across the owner’s workspace |
| `/{locale}/transactions/reconciliation` | Reconciliation records and decisions across the owner’s workspace |

The portfolio selector accepts a portfolio listed in the current owner's
registry. An unavailable selection requires choosing a portfolio again. Links
carry the portfolio and cost method across the accounting views. The
`portfolio` and `basis` query values support direct links. FIFO is the default.
Holdings and lots each show the result for the selected method. Rebuilding
requires confirmation and uses the existing projection-rebuild operation.
Journal entries are read-only on these pages.

## Imports and decisions

1. Select a CSV or Nexora JSON file, or paste its contents. Files are read in
   the browser as UTF-8 and the page waits for an explicit preview request.
   The complete UTF-8 request, including its JSON envelope, must fit within 1 MiB.
   Use the file format guide on the import page to check required fields.
2. Review row counts, browse every normalized row and check the reason for any
   flagged row. A quarantined row requires fixing the source and creating a
   fresh preview.
3. Approve the preview with a written reason and confirmation. Publication
   then requires recent passkey verification and separate confirmation. The
   existing atomic publication endpoint saves all ready rows together.
4. Review the case reference, choose an outcome and enter a reason for each
   open reconciliation case. The confirmation shows the specific case,
   outcome and reason. The request includes the case's expected row version
   and requires recent passkey verification. A version conflict refreshes the
   case for another review.

The UI uses the existing authenticated API and its CSRF client. All five pages
support Persian and English. This candidate preserves the existing accounting
and authentication contracts and makes no production readiness claim.

## Acceptance

```bash
.venv/bin/python scripts/verify_accounting_experience_ui.py
.venv/bin/python -m unittest discover -s tests -v
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e
```

The [candidate contract](../../contracts/nexora-v0.1-accounting-experience-ui.json)
requires successful CI on the candidate commit before recording `NEX-P4-06-FREEZE`.
That Freeze opens `NEX-P4-07`.
