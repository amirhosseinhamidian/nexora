#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any

from nexora.phase_one_acceptance import (
    PHASE_ONE_MAX_EVIDENCE_AGE,
    parse_capacity_report,
    parse_operations_drill_report,
    parse_phase_one_acceptance_record,
    serialize_phase_one_acceptance_record,
    sha256_bytes,
)
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIOR = ROOT / "artifacts/p1-12/private-deployment-operations-freeze.json"
DEFAULT_OUTPUT = ROOT / "artifacts/p1-13/phase-one-final-acceptance.json"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run fail-closed Nexora Phase 1 final acceptance gates")
    value.add_argument("--database-url", default=os.environ.get("NEXORA_ACCEPTANCE_DATABASE_URL"))
    value.add_argument("--confirm-destructive-migration-cycle", choices=("nexora_acceptance",), required=True)
    value.add_argument("--p1-12-record", type=Path, default=DEFAULT_PRIOR)
    value.add_argument("--capacity-report", type=Path, required=True)
    value.add_argument("--operations-drill-report", type=Path, required=True)
    value.add_argument("--github-actions-run-url", required=True)
    value.add_argument("--github-actions-head-sha", required=True)
    value.add_argument("--github-actions-conclusion", choices=("success",), required=True)
    for name in (
        "fresh-clone-install-smoke",
        "passkey-session-csrf-smoke",
        "trd-bot-sync-idempotency-smoke",
        "private-backup-restore-retention-smoke",
        "responsive-bilingual-web-shell-smoke",
        "no-forbidden-capabilities-smoke",
    ):
        value.add_argument(f"--{name}", choices=("pass",), required=True)
    value.add_argument("--environment-label", required=True)
    value.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return value


def _git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *arguments),
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def _identity() -> tuple[str, str]:
    sha = _git("rev-parse", "HEAD").stdout.strip().casefold()
    branch = _git("branch", "--show-current").stdout.strip()
    if not branch:
        raise ValueError("Phase 1 acceptance cannot run from detached HEAD")
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        raise ValueError("Phase 1 acceptance requires a clean worktree")
    return sha, branch


def _database_url(value: str | None) -> str:
    if not value:
        raise ValueError("--database-url or NEXORA_ACCEPTANCE_DATABASE_URL is required")
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or url.database != "nexora_acceptance":
        raise ValueError("destructive acceptance gates require PostgreSQL database nexora_acceptance")
    return value


def _command(label: str, command: tuple[str, ...], env: dict[str, str]) -> dict[str, Any]:
    started = monotonic()
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, check=False)
        code = result.returncode
    except OSError:
        code = 127
    safe = ("python", *command[1:]) if command and command[0] == sys.executable else command
    return {
        "label": label,
        "command": list(safe),
        "exit_code": code,
        "duration_ms": round((monotonic() - started) * 1000),
        "passed": code == 0,
    }


def _gate(gate_id: str, commands: tuple[tuple[str, tuple[str, ...]], ...], env: dict[str, str]) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for label, command in commands:
        item = _command(label, command, env)
        evidence.append(item)
        if not item["passed"]:
            break
    return {"gate_id": gate_id, "commands": evidence, "passed": all(item["passed"] for item in evidence)}


def _specs() -> tuple[tuple[str, tuple[tuple[str, tuple[str, ...]], ...]], ...]:
    python = sys.executable
    quality_paths = (
        "apps/server",
        "alembic",
        "scripts/benchmark_private_runtime.py",
        "scripts/record_private_operations_drill.py",
        "scripts/run_phase_one_final_acceptance.py",
        "scripts/verify_phase_one_final_acceptance.py",
        "tests/test_phase_one_final_acceptance.py",
    )
    return (
        (
            "repository_contract",
            (
                ("P1-13 contract verifier", (python, "scripts/verify_phase_one_final_acceptance.py")),
                ("Repository contract tests", (python, "-m", "unittest", "discover", "-s", "tests", "-q")),
            ),
        ),
        (
            "backend",
            (
                ("Backend format", (python, "-m", "ruff", "format", "--check", *quality_paths)),
                ("Backend lint", (python, "-m", "ruff", "check", *quality_paths)),
                ("Backend typing", (python, "-m", "mypy")),
                ("Backend tests", (python, "-m", "pytest", "-m", "not integration", "-q")),
            ),
        ),
        (
            "migration_cycle",
            (
                ("Alembic upgrade", (python, "-m", "alembic", "upgrade", "head")),
                ("Alembic downgrade", (python, "-m", "alembic", "downgrade", "base")),
                ("Alembic rebuild", (python, "-m", "alembic", "upgrade", "head")),
                ("Alembic drift", (python, "-m", "alembic", "check")),
            ),
        ),
        (
            "postgresql_resilience",
            (("PostgreSQL integration", (python, "-m", "pytest", "-m", "integration", "-q")),),
        ),
        (
            "frontend",
            (
                ("Frontend install", ("pnpm", "install", "--frozen-lockfile")),
                ("Frontend format", ("pnpm", "format:check")),
                ("Frontend lint", ("pnpm", "lint")),
                ("Frontend typecheck", ("pnpm", "typecheck")),
                ("Frontend tests", ("pnpm", "test")),
                ("Frontend build", ("pnpm", "build")),
            ),
        ),
        (
            "browser",
            (("Authenticated browser lifecycle", ("pnpm", "--filter", "@nexora/web", "test:e2e")),),
        ),
    )


def _artifact(path: Path, label: str) -> tuple[bytes, str]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be an absolute regular non-symbolic file")
    value = path.read_bytes()
    return value, sha256_bytes(value)


def _prior(path: Path) -> dict[str, Any]:
    value, _ = _artifact(path.resolve(), "P1-12 freeze record")
    record = json.loads(value)
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if sha256_bytes(canonical) != "49d9c3c2427d4154445a25c61be8945dca4b46cbcfe43ce25e538c37a457cda6":
        raise ValueError("P1-12 freeze record checksum drift")
    if record.get("candidate_commit_sha") != "86651f1b49343e7e609ee5f671ad00eb83822ca9":
        raise ValueError("P1-12 freeze candidate drift")
    if record.get("frozen") is not True or record.get("next_allowed_stage") != "NEX-P1-13":
        raise ValueError("P1-12 freeze does not authorize P1-13")
    outcome = _git("merge-base", "--is-ancestor", "1af9161925a71c4154801bb6ac4f533f4a8e21b8", "HEAD", check=False)
    if outcome.returncode != 0:
        raise ValueError("P1-12 freeze commit is not an ancestor of the candidate")
    return {
        "p1_12_record_checksum": "49d9c3c2427d4154445a25c61be8945dca4b46cbcfe43ce25e538c37a457cda6",
        "p1_12_commit_sha": "1af9161925a71c4154801bb6ac4f533f4a8e21b8",
        "p1_12_ready": True,
    }


def main() -> int:
    arguments = parser().parse_args()
    if arguments.output.exists():
        raise FileExistsError("Phase 1 acceptance output already exists")
    database_url = _database_url(arguments.database_url)
    candidate_sha, branch = _identity()
    if (
        re.fullmatch(
            r"https://github\.com/amirhosseinhamidian/nexora/actions/runs/[0-9]+", arguments.github_actions_run_url
        )
        is None
    ):
        raise ValueError("GitHub Actions URL must identify the Nexora candidate run")
    ci_sha = arguments.github_actions_head_sha.strip().casefold()
    if ci_sha != candidate_sha:
        raise ValueError("GitHub Actions head SHA must match the checked-out candidate")

    capacity_bytes, capacity_checksum = _artifact(arguments.capacity_report, "capacity report")
    drill_bytes, drill_checksum = _artifact(arguments.operations_drill_report, "operations drill report")
    capacity = parse_capacity_report(capacity_bytes)
    drill = parse_operations_drill_report(drill_bytes)
    reports = (capacity, drill)
    if any(report["candidate_commit_sha"] != candidate_sha for report in reports):
        raise ValueError("every acceptance report must match the checked-out candidate")
    if any(report["environment_label"] != arguments.environment_label for report in reports):
        raise ValueError("every acceptance report must match --environment-label")
    preflight_at = datetime.now(UTC)
    for report in reports:
        generated_at = datetime.fromisoformat(report["generated_at"].replace("Z", "+00:00")).astimezone(UTC)
        age = preflight_at - generated_at
        if age.total_seconds() < 0 or age > PHASE_ONE_MAX_EVIDENCE_AGE:
            raise ValueError("acceptance report evidence must be current")

    prior = _prior(arguments.p1_12_record)
    clean_environment = {key: value for key, value in os.environ.items() if not key.startswith("NEXORA_")}
    with tempfile.TemporaryDirectory(prefix="nexora-acceptance-") as temporary:
        dsn_path = Path(temporary) / "database.dsn"
        dsn_path.write_text(database_url + "\n", encoding="utf-8")
        dsn_path.chmod(0o600)
        clean_environment["NEXORA_MIGRATION_DATABASE_DSN_FILE"] = str(dsn_path)
        gates = tuple(_gate(gate_id, commands, clean_environment) for gate_id, commands in _specs())
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        raise ValueError("acceptance gates changed the candidate worktree")

    failed = [gate["gate_id"] for gate in gates if not gate["passed"]]
    manual = {
        "fresh_clone_install": arguments.fresh_clone_install_smoke,
        "passkey_session_and_csrf_lifecycle": arguments.passkey_session_csrf_smoke,
        "trd_bot_sync_and_idempotency": arguments.trd_bot_sync_idempotency_smoke,
        "private_backup_restore_and_retention": arguments.private_backup_restore_retention_smoke,
        "responsive_bilingual_web_shell": arguments.responsive_bilingual_web_shell_smoke,
        "no_forbidden_capabilities": arguments.no_forbidden_capabilities_smoke,
    }
    record: dict[str, Any] = {
        "schema_version": "nexora-phase-one-final-acceptance-record-v1",
        "candidate_commit_sha": candidate_sha,
        "branch": branch,
        "environment_label": arguments.environment_label,
        "generated_at": datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "prior_freeze": prior,
        "capacity": {
            "artifact_checksum": capacity_checksum,
            "candidate_commit_sha": capacity["candidate_commit_sha"],
            "environment_label": capacity["environment_label"],
            "generated_at": capacity["generated_at"],
            "passed": capacity["passed"],
        },
        "operations_drill": {
            "artifact_checksum": drill_checksum,
            "candidate_commit_sha": drill["candidate_commit_sha"],
            "environment_label": drill["environment_label"],
            "generated_at": drill["generated_at"],
            "passed": drill["passed"],
        },
        "ci": {
            "run_url": arguments.github_actions_run_url,
            "head_sha": ci_sha,
            "conclusion": arguments.github_actions_conclusion,
        },
        "manual": manual,
        "gates": list(gates),
        "failed_gates": failed,
        "ready_to_freeze_phase_one": not failed,
        "freeze_commit_policy": "acceptance-artifact-only",
        "security_boundary": {
            "public_internet_production_profile": False,
            "live_execution_capability": False,
            "exchange_credentials": False,
            "wallet_or_fund_transfer": False,
            "autonomous_ai_execution": False,
            "multi_user_identity": False,
        },
    }
    serialized = serialize_phase_one_acceptance_record(record) + "\n"
    parse_phase_one_acceptance_record(serialized.encode())
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("x", encoding="utf-8") as output:
        output.write(serialized)
    print(f"Wrote Phase 1 final acceptance record to {arguments.output}")
    return 0 if record["ready_to_freeze_phase_one"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
