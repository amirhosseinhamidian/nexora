#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from nexora.phase_two_acceptance import parse_phase_two_acceptance_record
from nexora.server_deployment_acceptance import (
    parse_capacity_report,
    parse_operations_drill_report,
    parse_server_deployment_acceptance_record,
    serialize_server_deployment_acceptance_record,
    sha256_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIOR = ROOT / "artifacts/p2-12/phase-two-final-acceptance.json"
DEFAULT_OUTPUT = ROOT / "artifacts/v0.1-server-acceptance/server-deployment-acceptance.json"
MAX_EVIDENCE_AGE = timedelta(days=7)
P2_12_FREEZE_COMMIT = "ffe5b1b50c6eb7b09bfe052ad96038de47b779df"
P2_12_RECORD_CHECKSUM = "114a660b358ba58e16cc3f2b885c20cc72d0b20e0d425f5c266dd2120c0daedb"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run fail-closed Nexora private VPS deployment acceptance")
    value.add_argument("--acceptance-profile", choices=("private_vps_de",), required=True)
    value.add_argument("--p2-12-record", type=Path, default=DEFAULT_PRIOR)
    value.add_argument("--operations-drill-report", type=Path, required=True)
    value.add_argument("--capacity-report", type=Path, required=True)
    value.add_argument("--github-actions-run-url", required=True)
    value.add_argument("--github-actions-head-sha", required=True)
    value.add_argument("--github-actions-conclusion", choices=("success",), required=True)
    for name in (
        "host-identity-country-review",
        "firewall-private-access-review",
        "ssh-hardening-review",
        "off-host-administration-separation-review",
        "clock-synchronization-review",
        "secret-file-permissions-review",
        "no-forbidden-capabilities-review",
    ):
        value.add_argument(f"--{name}", choices=("pass",), required=True)
    value.add_argument("--environment-label", required=True)
    value.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return value


def _git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(("git", *arguments), cwd=ROOT, check=check, capture_output=True, text=True)


def _identity() -> tuple[str, str]:
    sha = _git("rev-parse", "HEAD").stdout.strip().casefold()
    branch = _git("branch", "--show-current").stdout.strip()
    if not branch:
        raise ValueError("server acceptance cannot run from detached HEAD")
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        raise ValueError("server acceptance requires a clean worktree")
    return sha, branch


def _artifact(path: Path, label: str) -> tuple[bytes, str]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be an absolute regular non-symbolic file")
    value = path.read_bytes()
    return value, sha256_bytes(value)


def _fresh(generated_at: str, now: datetime, label: str) -> None:
    generated = datetime.fromisoformat(generated_at).astimezone(UTC)
    age = now - generated
    if age.total_seconds() < 0 or age > MAX_EVIDENCE_AGE:
        raise ValueError(f"{label} must be current and no more than seven days old")


def _prior(path: Path) -> dict[str, Any]:
    value, _ = _artifact(path.resolve(), "P2-12 acceptance record")
    record = parse_phase_two_acceptance_record(value)
    if record.get("record_checksum") != P2_12_RECORD_CHECKSUM:
        raise ValueError("P2-12 acceptance record checksum drift")
    if record.get("ready_to_freeze_phase_two") is not True or record.get("phase_two_scope_accepted") is not True:
        raise ValueError("P2-12 does not authorize server acceptance")
    outcome = _git("merge-base", "--is-ancestor", P2_12_FREEZE_COMMIT, "HEAD", check=False)
    if outcome.returncode != 0:
        raise ValueError("P2-12 Freeze commit is not an ancestor of the candidate")
    return {
        "p2_12_record_checksum": P2_12_RECORD_CHECKSUM,
        "p2_12_commit_sha": P2_12_FREEZE_COMMIT,
        "p2_12_ready": True,
    }


def main() -> int:
    arguments = parser().parse_args()
    if arguments.output.exists():
        raise FileExistsError("server deployment acceptance output already exists")
    if not arguments.environment_label.strip() or len(arguments.environment_label) > 80:
        raise ValueError("environment label must contain 1 to 80 characters")
    candidate_sha, branch = _identity()
    if (
        re.fullmatch(
            r"https://github\.com/amirhosseinhamidian/nexora/actions/runs/[0-9]+",
            arguments.github_actions_run_url,
        )
        is None
    ):
        raise ValueError("GitHub Actions URL must identify the Nexora candidate run")
    ci_sha = arguments.github_actions_head_sha.strip().casefold()
    if ci_sha != candidate_sha:
        raise ValueError("GitHub Actions head SHA must match the checked-out candidate")

    operations_bytes, operations_checksum = _artifact(arguments.operations_drill_report, "operations drill report")
    capacity_bytes, capacity_checksum = _artifact(arguments.capacity_report, "capacity report")
    operations = parse_operations_drill_report(operations_bytes)
    capacity = parse_capacity_report(capacity_bytes)
    now = datetime.now(UTC)
    for label, evidence in (
        ("operations drill", operations),
        ("capacity report", capacity),
    ):
        if evidence["candidate_commit_sha"] != candidate_sha:
            raise ValueError(f"{label} must match the checked-out candidate")
        if evidence["environment_label"] != arguments.environment_label:
            raise ValueError(f"{label} must match --environment-label")
        _fresh(evidence["generated_at"], now, label)
    prior = _prior(arguments.p2_12_record)

    manual = {
        "host_identity_and_country": arguments.host_identity_country_review,
        "firewall_and_private_access": arguments.firewall_private_access_review,
        "ssh_hardening": arguments.ssh_hardening_review,
        "off_host_administration_separation": arguments.off_host_administration_separation_review,
        "clock_synchronization": arguments.clock_synchronization_review,
        "secret_file_permissions": arguments.secret_file_permissions_review,
        "no_forbidden_capabilities": arguments.no_forbidden_capabilities_review,
    }
    gates = [
        {"gate_id": "p2_freeze", "passed": True},
        {"gate_id": "operations_drill", "passed": operations["passed"] is True},
        {"gate_id": "capacity_overload", "passed": capacity["passed"] is True},
        {
            "gate_id": "private_access",
            "passed": operations["private_deployment"]["passed"] is True,
        },
        {
            "gate_id": "candidate_ci",
            "passed": arguments.github_actions_conclusion == "success",
        },
        {
            "gate_id": "manual_hardening",
            "passed": all(value == "pass" for value in manual.values()),
        },
    ]
    failed = [gate["gate_id"] for gate in gates if not gate["passed"]]
    record: dict[str, Any] = {
        "schema_version": "nexora-server-deployment-acceptance-record-v1",
        "candidate_commit_sha": candidate_sha,
        "branch": branch,
        "acceptance_profile": arguments.acceptance_profile,
        "environment_label": arguments.environment_label,
        "generated_at": now.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "deployment_network_mode": "authenticated_private_overlay",
        "prior_freeze": prior,
        "operations_drill": {
            "artifact_checksum": operations_checksum,
            "candidate_commit_sha": operations["candidate_commit_sha"],
            "environment_label": operations["environment_label"],
            "generated_at": operations["generated_at"],
            "report_checksum": operations["report_checksum"],
            "backup_id": operations["backup"]["backup_id"],
            "restore_duration_seconds": operations["restore"]["duration_seconds"],
            "passed": operations["passed"],
        },
        "capacity": {
            "artifact_checksum": capacity_checksum,
            "candidate_commit_sha": capacity["candidate_commit_sha"],
            "environment_label": capacity["environment_label"],
            "generated_at": capacity["generated_at"],
            "report_checksum": capacity["report_checksum"],
            "completed_samples": capacity["completed_samples"],
            "throughput_per_second": capacity["throughput_per_second"],
            "latency_p95_ms": capacity["latency_p95_ms"],
            "passed": capacity["passed"],
        },
        "ci": {
            "run_url": arguments.github_actions_run_url,
            "head_sha": ci_sha,
            "conclusion": arguments.github_actions_conclusion,
        },
        "manual": manual,
        "gates": gates,
        "failed_gates": failed,
        "ready_to_freeze_server_deployment_acceptance": not failed,
        "server_deployment_accepted": not failed,
        "v0_1_private_release_unblocked": not failed,
        "production_readiness_scope": "private_single_owner_v0.1",
        "public_internet_production_readiness_claimed": False,
        "high_availability_claimed": False,
        "freeze_commit_policy": "acceptance-artifact-only",
        "security_boundary": {
            "public_internet_profile": False,
            "live_execution_capability": False,
            "exchange_credentials": False,
            "wallet_or_fund_transfer": False,
            "autonomous_ai_execution": False,
            "multi_user_identity": False,
        },
    }
    serialized = serialize_server_deployment_acceptance_record(record) + "\n"
    parse_server_deployment_acceptance_record(serialized.encode())
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("x", encoding="utf-8") as output:
        output.write(serialized)
    print(f"Wrote server deployment acceptance record to {arguments.output}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
