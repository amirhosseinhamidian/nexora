# NEX-P1-13 — Final Acceptance, Hardening and Freeze

Status: **Candidate tooling — execute only after commit, push and green CI**

This stage closes the local-foundation part of `NEX-P1-GAP-009`. It adds no
Portfolio feature and grants no new operational capability. Its purpose is to
bind local reference-host evidence, GitHub Actions and the full Phase 1
regression suite to one candidate SHA.

This acceptance is intentionally split in two. The current
`local_reference_foundation` profile may freeze Phase 1 and open `NEX-P2-01`,
but it is not production acceptance. The later
`NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE` gate must run on the private VPS آلمان
before the first v0.1 production deployment or release.

## Safety boundary

The migration cycle is destructive and may run only against a disposable
PostgreSQL 17 database named exactly `nexora_acceptance`. Never use the private
runtime database, a development database or a restored production copy. DSNs,
secret values and command output are not written to the acceptance artifact.

The candidate worktree must be clean and on a branch. Evidence must be no more
than seven days old and must share the candidate SHA and environment label.

The current local reference host uses the loopback-only (`loopback_only`)
profile: bind exactly
`127.0.0.1:443`, keep remote access disabled and require HTTPS. LAN, wildcard
and public exposure are rejected. The later VPS gate will choose and verify an
authenticated private network or an equivalently hardened server access model.

TRD Bot `0.3.0` is `legacy_read_only_blocked`, so the default reference runtime
must set `NEXORA_TRD_BOT_MODE=disabled_incompatible_provider`. No provider URL
or token is required or permitted for this mode. The adapter's contract,
negotiation, retry and idempotency tests remain mandatory, but Phase 1 does not
claim a live-provider sync. The compatible-provider override may be used only
for a `>=0.3.1,<0.4.0` provider after capability negotiation succeeds.

## Candidate CI

Commit and push all P1-13 tooling before producing host evidence. The
`Phase 1 final acceptance` workflow must be green on that SHA. Record its run
URL; rerunning a different SHA does not satisfy the gate.

## Capacity evidence

Deploy the candidate to the local reference host. Use its loopback HTTPS origin
and trusted CA, then run:

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
on every 429, no transport/5xx failure and no immutable-evidence loss. The
benchmark uses the external Caddy route `/api/v1/auth/session`; Caddy strips `/api`
before proxying the request to the API runtime.

## Deferred server deployment acceptance

The local Mac run must not pretend that a same-machine directory is an off-host
backup. `NEX-DEBT-P1-13-001` therefore keeps the server-only work in status
`deferred_to_server_deployment`. When the German VPS is provisioned, the
deployment gate must verify the hardened private access model, encrypted runtime
backup, an independent off-host copy, restore within the four-hour RTO,
retention dry-run, server capacity and overload, Worker restart/reclaim, and
post-restore session and service-token revocation.

The existing `record_private_operations_drill.py` remains the evidence recorder
for that later gate. Its report must be produced on the deployed VPS candidate;
it is not an input to the current local-reference acceptance runner.

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
  --acceptance-profile local_reference_foundation \
  --capacity-report /tmp/nexora-p1-13-capacity.json \
  --github-actions-run-url "$P1_13_GITHUB_ACTIONS_RUN_URL" \
  --github-actions-head-sha "$(git rev-parse HEAD)" \
  --github-actions-conclusion success \
  --trd-bot-provider-mode disabled_incompatible_provider \
  --fresh-clone-install-smoke pass \
  --passkey-session-csrf-smoke pass \
  --trd-bot-contract-idempotency-smoke pass \
  --responsive-bilingual-web-shell-smoke pass \
  --no-forbidden-capabilities-smoke pass \
  --environment-label macbook-pro-reference
```

The runner executes six ordered gates: repository contracts, backend quality
and tests, migration cycle, PostgreSQL resilience, frontend and browser. A
successful record has `ready_to_freeze_phase_one=true`, `failed_gates=[]`,
`production_readiness_claimed=false`, an explicitly deferred VPS gate and a
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

After the artifact-only Freeze and green CI, the Phase 1 foundation is complete
and the only next development stage is `NEX-P2-01`. This does not authorize a
v0.1 production deployment or release: the VPS gate remains blocking until it
passes on the actual German server. Portfolio features, SaaS/multi-user,
public-internet deployment, exchange credentials, wallets, live execution and
autonomous AI remain outside this acceptance.
