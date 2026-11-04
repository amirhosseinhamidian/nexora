# NEX-P2-12 — Acceptance, Hardening and Phase 2 Freeze

Status: **Candidate tooling — execute only after commit, push and green CI**

P2-12 adds no portfolio feature and grants no new operational capability. It
binds the complete Phase 2 accounting, PostgreSQL, export, browser, capacity and
security evidence to one candidate SHA before Phase 2 can be frozen.

## Acceptance boundary

The local profile is `local_reference_portfolio`. It may accept and freeze the
implemented Phase 2 scope, but it is not production acceptance. The existing
`NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE` gate remains blocking for v0.1
production deployment and release on the planned private German VPS.

The runner rejects detached or dirty worktrees, stale capacity evidence,
candidate/environment drift, failed CI and any database except the disposable
PostgreSQL 17 database named exactly `nexora_phase_two_acceptance`. DSNs,
credentials and command output are never written to the acceptance artifact.

## Evidence covered

The ordered gates verify:

- repository contracts and the complete P2-01 through P2-11 Freeze chain;
- backend format, lint, strict typing and non-integration regressions;
- upgrade, downgrade, rebuild and migration-drift detection;
- PostgreSQL owner isolation, journal immutability, concurrent idempotency,
  atomic import publication, FIFO/weighted-average rebuilds, NAV/P&L and export;
- scope and security inventories, including the absence of live execution;
- bilingual RTL/LTR Web format, lint, typechecking, tests and production build;
- Chromium acceptance for dashboard, journal, holdings, imports and
  reconciliation;
- current loopback-only capacity, overload and immutable-evidence protection.

## Candidate CI

Commit and push the P2-12 tooling first. The `Phase 2 final acceptance`
workflow must be green on that exact SHA. Record its run URL; a successful run
on another SHA does not satisfy this gate.

## Capacity evidence

Deploy the candidate to the local reference host and produce a current report:

```bash
export SOURCE_COMMIT_SHA="$(git rev-parse HEAD)"

uv run python scripts/benchmark_private_runtime.py \
  --base-url https://127.0.0.1 \
  --deployment-network-mode loopback_only \
  --ca-file /absolute/path/to/private-ca.pem \
  --requests 1000 \
  --concurrency 25 \
  --environment-label macbook-pro-reference \
  --output /tmp/nexora-p2-12-capacity.json
```

The report must match the candidate and environment, be no more than seven
days old, meet the frozen latency/throughput budgets, contain real 429 and
`Retry-After` evidence and report no immutable-evidence loss.

## Disposable PostgreSQL fixture

Use only a disposable database:

```bash
docker run --name nexora-p2-12-acceptance-db \
  --detach \
  --env POSTGRES_DB=nexora_phase_two_acceptance \
  --env POSTGRES_USER=nexora \
  --env POSTGRES_PASSWORD=nexora_acceptance_password \
  --publish 127.0.0.1:55435:5432 \
  postgres:17.6-alpine
```

If the container already exists, start it rather than creating a second one.
Never point the runner at a development, restored or production database.

## Final acceptance runner

Install the pinned Chromium once if needed, then run from a clean candidate
branch:

```bash
pnpm --filter @nexora/web exec playwright install chromium

export NEXORA_PHASE_TWO_ACCEPTANCE_DATABASE_URL='postgresql+psycopg://nexora:nexora_acceptance_password@127.0.0.1:55435/nexora_phase_two_acceptance'
export P2_12_GITHUB_ACTIONS_RUN_URL='https://github.com/amirhosseinhamidian/nexora/actions/runs/123456789'

uv run python scripts/run_phase_two_final_acceptance.py \
  --confirm-destructive-migration-cycle nexora_phase_two_acceptance \
  --acceptance-profile local_reference_portfolio \
  --capacity-report /tmp/nexora-p2-12-capacity.json \
  --github-actions-run-url "$P2_12_GITHUB_ACTIONS_RUN_URL" \
  --github-actions-head-sha "$(git rev-parse HEAD)" \
  --github-actions-conclusion success \
  --deterministic-accounting-fixture-review pass \
  --owner-scope-immutability-review pass \
  --import-reconciliation-atomicity-review pass \
  --projection-rebuild-export-review pass \
  --responsive-bilingual-portfolio-review pass \
  --no-forbidden-capabilities pass \
  --environment-label macbook-pro-reference
```

A successful record has `ready_to_freeze_phase_two=true`,
`phase_two_scope_accepted=true`, `failed_gates=[]`,
`production_readiness_claimed=false` and a valid `record_checksum`.

## Freeze policy

After success, `git status --short` must show only:

```text
?? artifacts/p2-12/phase-two-final-acceptance.json
```

The Freeze policy is `acceptance-artifact-only`. Do not commit capacity reports,
logs, DSNs, certificates, browser traces, databases or secret material. If any
gate fails, do not commit the failed record; fix the cause and rerun.

The artifact-only Freeze completes Phase 2, but it does not deploy, tag or
release v0.1. The only next operational stage is the deferred private-VPS
`NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE` gate.
