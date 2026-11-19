# NEX-P4-07 Decision Intelligence pages

The [Phase 4 roadmap](47-phase-four-product-experience-roadmap.md) assigns this
stage to Decision and Candidate evidence, risk explanations, portfolio impact,
bounded scenarios and human review history. The
[P4-06 Freeze](../../artifacts/p4-06/accounting-experience-ui-freeze.json) is
present at `3866c0b01b2a97f3987f86d5bec3f75e619d086b`.
[CI succeeded on that commit](https://github.com/amirhosseinhamidian/nexora/actions/runs/44411490611).

## Pages

| Path | Purpose |
| --- | --- |
| `/{locale}/decisions` | Browse the owner’s Decisions and Candidates, preview evidence and see its outcome journal |
| `/{locale}/decisions/records/{decision_id}` | Open Decision evidence directly |
| `/{locale}/decisions/candidates/{candidate_id}` | Open Candidate evidence and follow its linked Decision |

Both record paths support `/risk`, `/impact`, `/scenarios` and `/reviews`.
Pages and navigation work in Persian and English. The feed keeps its keyboard
controls and existing links to the monitoring workflow.

The Decision page searches the existing paginated owner feed. A Candidate
opens through its existing dedicated endpoint. Risk and portfolio impact
results must match the evidence generation before being displayed. Candidate
pages also check the Candidate carried by the result when supplied. The impact
page compares current and projected figures for the source’s simulated
portfolio. Scenarios show the fixed price shocks provided by the source.
An exact-value table accompanies the loss chart.

## Human reviews

Reviewers can accept, reject or defer with a localized reason and an optional
note. A custom reason requires a note. A deferred review can include a
future revisit time. The confirmation identifies the Decision, action,
reason and simulation mode before sending a request. A review only records
the owner’s assessment and carries no execution authority.

The request uses the current evidence generation, source checksum and review
version. An uncertain result can be retried with the same request and
idempotency key. A version conflict refreshes the history and requires a new
confirmation. After a successful write, a failed history refresh can be
retried independently. The history shows the reason, notes, date and provider
delivery status.

## Acceptance

```bash
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e

.venv/bin/python scripts/verify_decision_intelligence_ui.py
.venv/bin/python -m unittest discover -s tests -v
```

The [candidate contract](../../contracts/nexora-v0.1-decision-intelligence-ui.json)
requires CI on the candidate commit before `NEX-P4-07-FREEZE`. The Freeze
opens `NEX-P4-08` for Alerts, Watchlists and Outcome Journal.
