# NEX-P1-13 — Final Acceptance, Hardening and Freeze

Status: **Candidate tooling — execute only after commit, push and green CI**

This stage closes `NEX-P1-GAP-009`. It adds no Portfolio feature and grants no
new operational capability. Its purpose is to bind current host evidence,
GitHub Actions and the full Phase 1 regression suite to one candidate SHA.

## Safety boundary

The migration cycle is destructive and may run only against a disposable
PostgreSQL 17 database named exactly `nexora_acceptance`. Never use the private
runtime database, a development database or a restored production copy. DSNs,
secret values and command output are not written to the acceptance artifact.

The candidate worktree must be clean and on a branch. Evidence must be no more
than seven days old and must share the candidate SHA and environment label.

The reference host may use one of two bounded network modes:

- `loopback_only` (default): bind exactly `127.0.0.1:443`; remote access is
  disabled and no overlay client is required;
- `authenticated_private_overlay`: bind the authenticated overlay address when
  remote access is intentionally required.

Both modes require HTTPS and reject LAN-only, wildcard and public exposure.
The loopback-only mode is a stricter deployment of the frozen P1-12 topology;
it does not remove private-overlay support or reopen the earlier freeze.

## Candidate CI

Commit and push all P1-13 tooling before producing host evidence. The
`Phase 1 final acceptance` workflow must be green on that SHA. Record its run
URL; rerunning a different SHA does not satisfy the gate.

## Capacity evidence

Deploy the candidate to the private reference host. For the default local-only
mode, use its loopback HTTPS origin and trusted CA, then run:

```bash
export SOURCE_COMMIT_SHA="$(git rev-parse HEAD)"

uv run python scripts/benchmark_private_runtime.py \
  --base-url https://127.0.0.1 \
  --deployment-network-mode loopback_only \
  --ca-file /absolute/path/to/private-ca.pem \
  --requests 1000 \
  --concurrency 25 \
  --environment-label macbook-pro-reference \
  --output /tmp/nexora-p1-13-capacity.json
```

Success requires completed samples, actual HTTP 429 responses, `Retry-After`
on every 429, no transport/5xx failure and no immutable-evidence loss.

## Backup, restore and retention drill

Use the P1-12 runbook to create an encrypted backup, verify the independently
mounted off-site copy, restore into the disposable acceptance runtime, revoke
sessions and service tokens, rotate the scoped service token, run post-restore
health checks and restart/reclaim the Worker. Measure backup and restore wall
time. Run both retention commands without `--apply` and retain their two plan
files.

With the measured values and real evidence paths, create the drill report:

```bash
uv run python scripts/record_private_operations_drill.py \
  --environment-label macbook-pro-reference \
  --runtime-backup-root /absolute/path/to/runtime-backups \
  --offsite-backup-root /absolute/path/to/offsite-backups \
  --backup-id YYYYMMDDTHHMMSSZ-1234abcd \
  --artifact-retention-plan /absolute/path/to/YYYYMMDD.artifacts.dry-run.plan.json \
  --backup-retention-plan /absolute/path/to/YYYYMMDD.backups.dry-run.plan.json \
  --backup-duration-seconds 12.5 \
  --restore-duration-seconds 42.8 \
  --deployment-network-mode loopback_only \
  --database-restore-smoke pass \
  --artifact-restore-smoke pass \
  --session-revocation-smoke pass \
  --service-token-revocation-smoke pass \
  --service-token-rotation-smoke pass \
  --post-restore-health-smoke pass \
  --private-deployment-smoke pass \
  --worker-restart-reclaim-smoke pass \
  --output /tmp/nexora-p1-13-operations-drill.json
```

The recorder validates both encrypted copies and retention plans directly. A
`pass` flag is an owner attestation and must only be supplied after the named
smoke check actually succeeds. Use `authenticated_private_overlay` instead of
`loopback_only` only when the benchmark and deployment actually use that mode.

## Final acceptance runner

Create and migrate a disposable database named `nexora_acceptance`. Install the
pinned Playwright browser once if it is not already present:

```bash
pnpm --filter @nexora/web exec playwright install chromium
```

Then run the final gates from a clean candidate branch:

```bash
export NEXORA_ACCEPTANCE_DATABASE_URL='postgresql+psycopg://nexora:password@127.0.0.1:5432/nexora_acceptance'
export P1_13_GITHUB_ACTIONS_RUN_URL='https://github.com/amirhosseinhamidian/nexora/actions/runs/123456789'

uv run python scripts/run_phase_one_final_acceptance.py \
  --confirm-destructive-migration-cycle nexora_acceptance \
  --capacity-report /tmp/nexora-p1-13-capacity.json \
  --operations-drill-report /tmp/nexora-p1-13-operations-drill.json \
  --github-actions-run-url "$P1_13_GITHUB_ACTIONS_RUN_URL" \
  --github-actions-head-sha "$(git rev-parse HEAD)" \
  --github-actions-conclusion success \
  --fresh-clone-install-smoke pass \
  --passkey-session-csrf-smoke pass \
  --trd-bot-sync-idempotency-smoke pass \
  --private-backup-restore-retention-smoke pass \
  --responsive-bilingual-web-shell-smoke pass \
  --no-forbidden-capabilities-smoke pass \
  --environment-label macbook-pro-reference
```

The runner executes six ordered gates: repository contracts, backend quality
and tests, migration cycle, PostgreSQL resilience, frontend and browser. A
successful record has `ready_to_freeze_phase_one=true`, `failed_gates=[]` and a
valid `record_checksum`.

## Freeze policy

After success, `git status --short` must show only:

```text
?? artifacts/p1-13/phase-one-final-acceptance.json
```

The Freeze commit policy is `acceptance-artifact-only`. Do not include logs,
capacity reports, drill reports, DSNs, certificates, backup material or secret
files. If any gate fails, do not commit the failed artifact; correct the cause
and rerun with a new output.

After the artifact-only Freeze and green CI, Phase 1 is complete and the only
next development stage is `NEX-P2-01`. Portfolio features, SaaS/multi-user,
public-internet deployment, exchange credentials, wallets, live execution and
autonomous AI remain outside this acceptance.
