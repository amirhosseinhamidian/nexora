# NEX-P4-12 Phase 4 final acceptance

P4-12 assembles the final acceptance record for the local, single-owner
Nexora v0.1 experience. The [P4-11 Freeze](../../artifacts/p4-11/phase-four-product-acceptance-freeze.json)
is committed at `87f2eb4d48d033d879c6fe9998b46fa99ae56c94`. Its
[GitHub Actions run](https://github.com/amirhosseinhamidian/nexora/actions/runs/44513286286)
passed.

## Evidence

| Gate | Evidence |
| --- | --- |
| Phase 4 contracts | Canonical hashes and transitions for P4-00 through P4-11, plus the repository contract tests |
| Backend | Type checking, backend tests and generated runtime contract verification |
| PostgreSQL 17 | Upgrade from an empty database, integration tests, downgrade, rebuild and migration drift check in an isolated CI database |
| Web and reconciliation | Web formatting, lint, type checking, unit tests and accounting paths in Chromium |
| Private scope and security | Scope, security inventory and integration contract verification |
| Product journeys | Chromium acceptance and its integrity-checked evidence file for the P4-12 candidate |
| Manual appearance | The owner's 16 confirmed profiles from P4-11, carried forward when the reviewed product files match |

The CI gates use successful push runs and required jobs and steps from the
same P4-12 candidate SHA. The verifier compares that candidate's tracked
product files with the files accepted in P4-11. This keeps the owner's
visual review bound to the version they inspected.

The [contract](../../contracts/nexora-v0.1-phase-four-final-acceptance.json)
records the limitations of Chromium fixtures, provider compatibility,
sampled analytics and browser-local export receipts. The roadmap's full
deferred inventory carries forward. The private VPS acceptance gate
continues to apply before v0.1 production deployment and release, and
`production_readiness_claimed=false` is required in the final record.

## Verify the candidate locally

```zsh
fnm exec --using 24.22.1 ./apps/web/node_modules/.bin/prettier \
  --config apps/web/prettier.config.mjs --write \
  contracts/nexora-v0.1-phase-four-final-acceptance.json \
  .github/workflows/phase-four-final-acceptance.yml

.venv/bin/python scripts/verify_phase_four_final_acceptance.py
.venv/bin/python -m unittest discover -s tests -v
```

## Record and freeze

Commit and push the candidate first. When its required CI jobs are green,
collect their official run, job and step results, with the browser report and
the GitHub artifact digest from the same run.

The JSON input for `capture` contains `workflows` keyed by workflow path.
Each workflow includes `run_id`, `attempt`, `head_sha`, `head_branch`,
`event`, `conclusion` and `jobs`. Each referenced job includes `job_id`,
`head_sha`, `run_attempt`, `conclusion` and `steps` keyed by step name with its
conclusion as the value. Pass the verified report as `browser_evidence` and
its `name`, `artifact_id`, `run_id` and `digest` as `browser_artifact`.

From a clean checkout of the candidate, capture and validate the final record.

```zsh
mkdir -p artifacts/p4-12
.venv/bin/python scripts/verify_phase_four_final_acceptance.py capture \
  /tmp/nexora-p4-12-ci-evidence.json artifacts/p4-12/phase-four-final-acceptance.json
.venv/bin/python scripts/verify_phase_four_final_acceptance.py verify-record
```

A valid record lists the passed gates and contains
`ready_to_freeze_phase_four=true`, `phase_four_scope_accepted=true`,
`failed_gates=[]` and its canonical SHA-256 checksum. Commit the validated
record as the final Phase 4 Freeze.
