# NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE

Status: **Candidate tooling — execute only after commit, push and green CI**

This gate closes `NEX-DEBT-P1-13-001`. It adds no Portfolio feature and does
not widen the frozen security boundary. It accepts one exact Nexora candidate
for the private, single-owner v0.1 runtime on the planned German VPS.

Passing this gate may unblock the private v0.1 release candidate. It does not
claim public-internet, high-availability, SaaS, multi-user, live-trading,
wallet, fund-transfer or autonomous-AI readiness.

## Required topology

- host type: `private_vps`;
- country code: `DE`;
- access: authenticated private overlay or an equivalently hardened private
  access model recorded as `authenticated_private_overlay`;
- application exposure: HTTPS 443 only on the private interface;
- PostgreSQL, Worker and internal service ports are never host-published;
- public network exposure remains false;
- TLS minimum remains 1.3.

The candidate SHA must descend from the Phase 2 Freeze commit
`ffe5b1b50c6eb7b09bfe052ad96038de47b779df`. The worktree must be clean and
all evidence must name the same candidate SHA and environment label.

## Evidence set

Evidence may be no more than seven days old:

1. green GitHub Actions run for the candidate;
2. server capacity report with at least 1000 completed samples, actual 429
   overload responses, `Retry-After` on every 429, throughput at least 10/s,
   p95 no more than 300 ms, no transport/5xx failure and no evidence loss;
3. encrypted runtime backup plus a matching independently administered or
   mounted off-host copy;
4. owner-attended restore within four hours;
5. database and artifact restore smoke;
6. post-restore session revocation, service-token revocation and rotation;
7. protected artifact and backup retention dry-runs;
8. private deployment, health, Web shell and Worker restart/reclaim smoke.

A second directory on the VPS is not off-host. The age private identity must
not remain on the runtime host at rest. Evidence and acceptance artifacts must
not contain DSNs, secret values, private keys, certificates, backup payloads or
raw command output.

## Candidate workflow

Commit and push this tooling first. The `Server deployment acceptance`
workflow and all regression workflows must be green on the candidate SHA.
Deploy that exact SHA to the VPS before collecting operational evidence.

Use an environment label that identifies the server without disclosing an IP,
for example `de-private-vps-reference`.

## Capacity report

From a trusted client connected to the private overlay:

```bash
export SOURCE_COMMIT_SHA="$(git rev-parse HEAD)"

uv run python scripts/benchmark_private_runtime.py \
  --base-url https://PRIVATE_NEXORA_ORIGIN \
  --deployment-network-mode authenticated_private_overlay \
  --ca-file /absolute/path/to/private-ca.pem \
  --requests 1000 \
  --concurrency 25 \
  --environment-label de-private-vps-reference \
  --output /absolute/evidence/private-runtime-capacity.json
```

The origin must resolve only through the approved private access path. Do not
replace this with a public DNS or public bind for convenience.

## Operations drill

Create the encrypted backup, copy it to an independent off-host target, run an
owner-attended restore and generate protected retention dry-runs. Record the
result with the existing evidence recorder:

```bash
uv run python scripts/record_private_operations_drill.py \
  --environment-label de-private-vps-reference \
  --runtime-backup-root /absolute/runtime/backups \
  --offsite-backup-root /absolute/mounted-or-administered-offhost/backups \
  --backup-id BACKUP_ID \
  --artifact-retention-plan /absolute/evidence/artifact-retention-plan.json \
  --backup-retention-plan /absolute/evidence/backup-retention-plan.json \
  --backup-duration-seconds BACKUP_SECONDS \
  --restore-duration-seconds RESTORE_SECONDS \
  --deployment-network-mode authenticated_private_overlay \
  --database-restore-smoke pass \
  --artifact-restore-smoke pass \
  --session-revocation-smoke pass \
  --service-token-revocation-smoke pass \
  --service-token-rotation-smoke pass \
  --post-restore-health-smoke pass \
  --private-deployment-smoke pass \
  --worker-restart-reclaim-smoke pass \
  --output /absolute/evidence/private-operations-drill.json
```

## Final runner

After the candidate CI and both evidence files pass:

```bash
uv run python scripts/run_server_deployment_acceptance.py \
  --acceptance-profile private_vps_de \
  --operations-drill-report /absolute/evidence/private-operations-drill.json \
  --capacity-report /absolute/evidence/private-runtime-capacity.json \
  --github-actions-run-url https://github.com/amirhosseinhamidian/nexora/actions/runs/RUN_ID \
  --github-actions-head-sha "$(git rev-parse HEAD)" \
  --github-actions-conclusion success \
  --host-identity-country-review pass \
  --firewall-private-access-review pass \
  --ssh-hardening-review pass \
  --off-host-administration-separation-review pass \
  --clock-synchronization-review pass \
  --secret-file-permissions-review pass \
  --no-forbidden-capabilities-review pass \
  --environment-label de-private-vps-reference
```

Success requires `failed_gates=[]`,
`ready_to_freeze_server_deployment_acceptance=true`,
`server_deployment_accepted=true`, `v0_1_private_release_unblocked=true` and a
valid checksum. Public readiness and high availability remain false.

## Freeze policy

After success, `git status --short` must show only:

```text
?? artifacts/v0.1-server-acceptance/server-deployment-acceptance.json
```

The Freeze commit is acceptance-artifact-only. Do not commit capacity reports,
operations drill reports, retention plans, logs, DSNs, certificates, backup
material or secrets. If any gate fails, preserve the failed report outside the
repository, correct the cause and rerun from a clean candidate.

After the artifact-only Freeze and green CI, the only next delivery stage is
`NEX-V0.1-RELEASE-CANDIDATE` within the frozen private single-owner scope.
