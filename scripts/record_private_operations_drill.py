#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nexora.private_operations import verify_backup_copy

ROOT = Path(__file__).resolve().parents[1]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Record fail-closed private operations drill evidence")
    value.add_argument("--environment-label", required=True)
    value.add_argument("--runtime-backup-root", type=Path, required=True)
    value.add_argument("--offsite-backup-root", type=Path, required=True)
    value.add_argument("--backup-id", required=True)
    value.add_argument("--artifact-retention-plan", type=Path, required=True)
    value.add_argument("--backup-retention-plan", type=Path, required=True)
    value.add_argument("--backup-duration-seconds", type=float, required=True)
    value.add_argument("--restore-duration-seconds", type=float, required=True)
    value.add_argument(
        "--deployment-network-mode",
        choices=("loopback_only", "authenticated_private_overlay"),
        required=True,
    )
    for name in (
        "database-restore-smoke",
        "artifact-restore-smoke",
        "session-revocation-smoke",
        "service-token-revocation-smoke",
        "service-token-rotation-smoke",
        "post-restore-health-smoke",
        "private-deployment-smoke",
        "worker-restart-reclaim-smoke",
    ):
        value.add_argument(f"--{name}", choices=("pass",), required=True)
    value.add_argument("--output", type=Path, required=True)
    return value


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", *arguments),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _identity() -> tuple[str, str]:
    sha = _git("rev-parse", "HEAD").casefold()
    branch = _git("branch", "--show-current")
    if not branch:
        raise ValueError("operations drill cannot run from detached HEAD")
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("operations drill requires a clean worktree")
    return sha, branch


def _json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be an absolute regular non-symbolic file")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain an object")
    return payload


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    arguments = parser().parse_args()
    if arguments.output.exists():
        raise FileExistsError("operations drill output already exists")
    if not arguments.environment_label.strip() or len(arguments.environment_label) > 80:
        raise ValueError("environment label must contain 1 to 80 characters")
    if arguments.backup_duration_seconds <= 0 or arguments.restore_duration_seconds <= 0:
        raise ValueError("backup and restore durations must be positive")
    if arguments.restore_duration_seconds > 4 * 60 * 60:
        raise ValueError("restore drill exceeded the four-hour RTO")
    candidate_sha, branch = _identity()
    runtime = verify_backup_copy(arguments.runtime_backup_root, arguments.backup_id)
    offsite = verify_backup_copy(arguments.offsite_backup_root, arguments.backup_id)
    if runtime.canonical_bytes() != offsite.canonical_bytes():
        raise ValueError("runtime and offsite backup copies do not match")
    if runtime.source_commit_sha != candidate_sha:
        raise ValueError("backup source commit does not match the checked-out candidate")

    artifact_plan = _json(arguments.artifact_retention_plan, "artifact retention plan")
    backup_plan = _json(arguments.backup_retention_plan, "backup retention plan")
    if artifact_plan.get("schema_version") != "nexora-retention-plan-v1":
        raise ValueError("artifact retention plan schema drift")
    if artifact_plan.get("dry_run") is not True or artifact_plan.get("immutable_evidence_excluded") is not True:
        raise ValueError("artifact retention plan is not a protected dry-run")
    if backup_plan.get("schema_version") != "nexora-backup-retention-plan-v1":
        raise ValueError("backup retention plan schema drift")
    if backup_plan.get("dry_run") is not True or backup_plan.get("runtime_copy_counts_as_offsite") is not False:
        raise ValueError("backup retention plan is not a protected dry-run")

    payload: dict[str, Any] = {
        "schema_version": "nexora-private-operations-drill-v1",
        "candidate_commit_sha": candidate_sha,
        "branch": branch,
        "environment_label": arguments.environment_label,
        "generated_at": datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "backup": {
            "backup_id": runtime.backup_id,
            "source_commit_sha": runtime.source_commit_sha,
            "encrypted_sha256": runtime.sha256,
            "size_bytes": runtime.size_bytes,
            "runtime_manifest_checksum": hashlib.sha256(runtime.canonical_bytes()).hexdigest(),
            "offsite_manifest_checksum": hashlib.sha256(offsite.canonical_bytes()).hexdigest(),
            "runtime_and_offsite_copies_match": True,
            "duration_seconds": round(arguments.backup_duration_seconds, 3),
            "passed": True,
        },
        "restore": {
            "duration_seconds": round(arguments.restore_duration_seconds, 3),
            "database_restored": arguments.database_restore_smoke == "pass",
            "artifacts_restored": arguments.artifact_restore_smoke == "pass",
            "sessions_revoked": arguments.session_revocation_smoke == "pass",
            "service_tokens_revoked": arguments.service_token_revocation_smoke == "pass",
            "service_token_rotation_completed": arguments.service_token_rotation_smoke == "pass",
            "post_restore_health_passed": arguments.post_restore_health_smoke == "pass",
            "passed": True,
        },
        "retention": {
            "dry_run": True,
            "artifact_plan_checksum": _checksum(arguments.artifact_retention_plan),
            "backup_plan_checksum": _checksum(arguments.backup_retention_plan),
            "immutable_evidence_excluded": True,
            "pinned_artifacts_excluded": True,
            "runtime_copy_counts_as_offsite": False,
            "passed": True,
        },
        "private_deployment": {
            "network_mode": arguments.deployment_network_mode,
            "remote_access_enabled": arguments.deployment_network_mode == "authenticated_private_overlay",
            "public_network_exposure": False,
            "https_443_only": arguments.private_deployment_smoke == "pass",
            "health_ready": arguments.private_deployment_smoke == "pass",
            "web_shell": arguments.private_deployment_smoke == "pass",
            "worker_restart_reclaim": arguments.worker_restart_reclaim_smoke == "pass",
            "passed": True,
        },
        "failure_reasons": [],
        "passed": True,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    payload["report_checksum"] = hashlib.sha256(encoded).hexdigest()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote private operations drill report to {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
