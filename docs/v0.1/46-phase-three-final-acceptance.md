# NEX-P3-13 — Phase 3 Acceptance and Freeze

Status: **Candidate tooling — execute only after commit, push and green CI**

P3-13 adds no product feature, API route, database table or migration. It binds
the complete Phase 3 Decision Intelligence implementation and its acceptance
evidence to one candidate SHA before Phase 3 can be frozen.

## Prerequisite

P3-12 is accepted at
`7fb3a707dc6b3c059eb2e65b06490385f18c3b1b`. Its same-SHA CI acceptance opens
only P3-13. The Phase 3 acceptance candidate must descend from that commit and
must preserve the complete P3-03 through P3-12 contract chain.

## Evidence covered

The fail-closed acceptance gates verify:

- repository contracts and the complete P3-03 through P3-12 chain;
- backend format, lint, strict typing, runtime-contract drift and regressions;
- PostgreSQL 17 migration from zero, downgrade, rebuild and migration drift;
- owner-scoped projection persistence, duplicate delivery, idempotent replay,
  aggregate-gap handling, quarantine and full-resync recovery;
- private-complete and AI-safe export coverage, checksums, lineage and
  redaction;
- scope, integration and security inventories;
- bilingual responsive Web format, lint, typechecking, tests and build;
- Chromium fixture E2E, keyboard navigation and explicit empty, error and
  degraded states;
- the immutable TRD Bot 0.3.1 real local-provider smoke evidence already bound
  by P3-03.

The provider evidence is fixed to provider commit
`3097276ed77cd212101797654452456b7fbc61de`, workflow run `43210235551`,
artifact `13939958030` and digest
`sha256:d1ec79aa429891ae94a36a4d65d573c3b97550ceaffa343b3df8989286d3375d`.
P3-13 validates and binds this evidence; it does not replace it with fixture
evidence or silently claim a new provider smoke.

## Candidate CI

Commit and push the P3-13 tooling first. The `Phase 3 final acceptance`
workflow must be green on that exact SHA. A successful workflow on another SHA
does not satisfy acceptance.

## Disposable PostgreSQL fixture

The final runner performs a destructive migration cycle. Use only a disposable
database named exactly `nexora_phase_three_acceptance`:

```bash
docker run --name nexora-p3-13-acceptance-db \
  --detach \
  --env POSTGRES_DB=nexora_phase_three_acceptance \
  --env POSTGRES_USER=nexora \
  --env POSTGRES_PASSWORD=nexora_acceptance_password \
  --publish 127.0.0.1:55436:5432 \
  postgres:17.6-alpine
```

If the container already exists, start it rather than creating another one.
Never target a development, restored or production database.

## Final acceptance runner

Install the pinned Chromium once if needed, then run from the clean candidate
branch after same-SHA CI succeeds:

```bash
pnpm --filter @nexora/web exec playwright install chromium

export NEXORA_PHASE_THREE_ACCEPTANCE_DATABASE_URL='postgresql+psycopg://nexora:nexora_acceptance_password@127.0.0.1:55436/nexora_phase_three_acceptance'
export P3_13_GITHUB_ACTIONS_RUN_URL='https://github.com/amirhosseinhamidian/nexora/actions/runs/123456789'

uv run python scripts/run_phase_three_final_acceptance.py \
  --confirm-destructive-migration-cycle nexora_phase_three_acceptance \
  --acceptance-profile local_reference_decision_intelligence \
  --github-actions-run-url "$P3_13_GITHUB_ACTIONS_RUN_URL" \
  --github-actions-head-sha "$(git rev-parse HEAD)" \
  --github-actions-conclusion success \
  --projection-replay-and-recovery-review pass \
  --owner-scope-and-immutability-review pass \
  --export-lineage-and-redaction-review pass \
  --responsive-bilingual-accessibility-review pass \
  --compatible-provider-smoke-review pass \
  --no-forbidden-capabilities pass \
  --environment-label macbook-pro-reference
```

A successful record has `ready_to_freeze_phase_three=true`,
`phase_three_scope_accepted=true`, `failed_gates=[]`,
`production_readiness_claimed=false` and a valid `record_checksum`. DSNs,
credentials, command output, browser traces and databases are not written to
the record.

## Freeze policy

After success, `git status --short` must show only:

```text
?? artifacts/p3-13/phase-three-final-acceptance.json
```

The Freeze policy is `acceptance-artifact-only`. Commit only that generated
record. If any gate fails, do not commit the failed record; fix the cause and
rerun from a clean candidate checkout.

The artifact-only Freeze completes Phase 3, but it does not deploy, tag or
release v0.1. `NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE` remains deferred until a
private German VPS is available and continues to block production deployment
and the v0.1 release. Local Phase 3 acceptance is not production acceptance.
