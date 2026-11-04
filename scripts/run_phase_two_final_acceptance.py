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

from nexora.phase_one_acceptance import PHASE_ONE_MAX_EVIDENCE_AGE, parse_capacity_report, sha256_bytes
from nexora.phase_two_acceptance import parse_phase_two_acceptance_record, serialize_phase_two_acceptance_record
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIOR = ROOT / "artifacts/p2-11/transactions-holdings-reconciliation-ui-freeze.json"
DEFAULT_OUTPUT = ROOT / "artifacts/p2-12/phase-two-final-acceptance.json"
P2_11_FREEZE_CHECKSUM = "e8070032a9579a0545847994e9bb0b426310f110ec6c3a0983db2a755d36be1c"
P2_11_FREEZE_COMMIT = "df6e05aa4d71a9f8b844e4c1b333449223e7dff3"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run fail-closed Nexora Phase 2 final acceptance gates")
    value.add_argument("--database-url", default=os.environ.get("NEXORA_PHASE_TWO_ACCEPTANCE_DATABASE_URL"))
    value.add_argument(
        "--confirm-destructive-migration-cycle",
        choices=("nexora_phase_two_acceptance",),
        required=True,
    )
    value.add_argument("--p2-11-record", type=Path, default=DEFAULT_PRIOR)
    value.add_argument("--acceptance-profile", choices=("local_reference_portfolio",), required=True)
    value.add_argument("--capacity-report", type=Path, required=True)
    value.add_argument("--github-actions-run-url", required=True)
    value.add_argument("--github-actions-head-sha", required=True)
    value.add_argument("--github-actions-conclusion", choices=("success",), required=True)
    for name in (
        "deterministic-accounting-fixture-review",
        "owner-scope-immutability-review",
        "import-reconciliation-atomicity-review",
        "projection-rebuild-export-review",
        "responsive-bilingual-portfolio-review",
        "no-forbidden-capabilities",
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
        raise ValueError("Phase 2 acceptance cannot run from detached HEAD")
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        raise ValueError("Phase 2 acceptance requires a clean worktree")
    return sha, branch


def _database_url(value: str | None) -> str:
    if not value:
        raise ValueError("--database-url or NEXORA_PHASE_TWO_ACCEPTANCE_DATABASE_URL is required")
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or url.database != "nexora_phase_two_acceptance":
        raise ValueError("destructive acceptance gates require PostgreSQL database nexora_phase_two_acceptance")
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
        "scripts/run_phase_two_final_acceptance.py",
        "scripts/verify_phase_two_final_acceptance.py",
        "tests/test_phase_two_final_acceptance.py",
    )
    return (
        (
            "repository_contract",
            (
                ("P2-12 contract verifier", (python, "scripts/verify_phase_two_final_acceptance.py")),
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
            "postgresql_accounting",
            (("PostgreSQL accounting and concurrency", (python, "-m", "pytest", "-m", "integration", "-q")),),
        ),
        (
            "security_inventory",
            (
                ("Scope boundary", (python, "scripts/verify_scope_contract.py")),
                ("Security boundary", (python, "scripts/verify_security_boundary.py")),
                ("Phase 2 domain", (python, "scripts/verify_phase_two_portfolio_domain.py")),
                (
                    "Transactions holdings reconciliation UI",
                    (python, "scripts/verify_transactions_holdings_reconciliation_ui.py"),
                ),
            ),
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
        ("browser", (("Portfolio browser acceptance", ("pnpm", "--filter", "@nexora/web", "test:e2e")),)),
    )


def _artifact(path: Path, label: str) -> tuple[bytes, str]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be an absolute regular non-symbolic file")
    value = path.read_bytes()
    return value, sha256_bytes(value)


def _prior(path: Path) -> dict[str, Any]:
    value, _ = _artifact(path.resolve(), "P2-11 Freeze record")
    record = json.loads(value)
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if sha256_bytes(canonical) != P2_11_FREEZE_CHECKSUM:
        raise ValueError("P2-11 Freeze record checksum drift")
    if record.get("candidate_commit_sha") != "ef65e02e2d257b0f69277db19e96d23443b77ef2":
        raise ValueError("P2-11 accepted candidate drift")
    if record.get("frozen") is not True or record.get("next_allowed_stage") != "NEX-P2-12":
        raise ValueError("P2-11 Freeze does not authorize P2-12")
    if _git("merge-base", "--is-ancestor", P2_11_FREEZE_COMMIT, "HEAD", check=False).returncode != 0:
        raise ValueError("P2-11 Freeze commit is not an ancestor of the candidate")
    return {
        "p2_11_record_checksum": P2_11_FREEZE_CHECKSUM,
        "p2_11_commit_sha": P2_11_FREEZE_COMMIT,
        "p2_11_ready": True,
    }


def main() -> int:
    arguments = parser().parse_args()
    if arguments.output.exists():
        raise FileExistsError("Phase 2 acceptance output already exists")
    database_url = _database_url(arguments.database_url)
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

    capacity_bytes, capacity_checksum = _artifact(arguments.capacity_report, "capacity report")
    capacity = parse_capacity_report(capacity_bytes)
    if capacity["candidate_commit_sha"] != candidate_sha:
        raise ValueError("capacity report must match the checked-out candidate")
    if capacity["environment_label"] != arguments.environment_label:
        raise ValueError("capacity report must match --environment-label")
    if capacity["deployment_network_mode"] != "loopback_only":
        raise ValueError("Phase 2 local acceptance requires loopback_only deployment")
    now = datetime.now(UTC)
    generated_at = datetime.fromisoformat(capacity["generated_at"].replace("Z", "+00:00")).astimezone(UTC)
    age = now - generated_at
    if age.total_seconds() < 0 or age > PHASE_ONE_MAX_EVIDENCE_AGE:
        raise ValueError("capacity evidence must be current")

    prior = _prior(arguments.p2_11_record)
    clean_environment = {key: value for key, value in os.environ.items() if not key.startswith("NEXORA_")}
    with tempfile.TemporaryDirectory(prefix="nexora-phase-two-acceptance-") as temporary:
        dsn_path = Path(temporary) / "database.dsn"
        dsn_path.write_text(database_url + "\n", encoding="utf-8")
        dsn_path.chmod(0o600)
        clean_environment["NEXORA_MIGRATION_DATABASE_DSN_FILE"] = str(dsn_path)
        gates = tuple(_gate(gate_id, commands, clean_environment) for gate_id, commands in _specs())
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        raise ValueError("acceptance gates changed the candidate worktree")

    failed = [gate["gate_id"] for gate in gates if not gate["passed"]]
    manual = {
        "deterministic_accounting_fixture_review": arguments.deterministic_accounting_fixture_review,
        "owner_scope_and_immutability_review": arguments.owner_scope_immutability_review,
        "import_reconciliation_atomicity_review": arguments.import_reconciliation_atomicity_review,
        "projection_rebuild_and_export_review": arguments.projection_rebuild_export_review,
        "responsive_bilingual_portfolio_review": arguments.responsive_bilingual_portfolio_review,
        "no_forbidden_capabilities": arguments.no_forbidden_capabilities,
    }
    record: dict[str, Any] = {
        "schema_version": "nexora-phase-two-final-acceptance-record-v1",
        "candidate_commit_sha": candidate_sha,
        "branch": branch,
        "acceptance_profile": arguments.acceptance_profile,
        "environment_label": arguments.environment_label,
        "generated_at": datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "prior_freeze": prior,
        "capacity": {
            "artifact_checksum": capacity_checksum,
            "candidate_commit_sha": capacity["candidate_commit_sha"],
            "environment_label": capacity["environment_label"],
            "deployment_network_mode": capacity["deployment_network_mode"],
            "generated_at": capacity["generated_at"],
            "passed": capacity["passed"],
        },
        "ci": {
            "run_url": arguments.github_actions_run_url,
            "head_sha": ci_sha,
            "conclusion": arguments.github_actions_conclusion,
        },
        "manual": manual,
        "gates": list(gates),
        "failed_gates": failed,
        "ready_to_freeze_phase_two": not failed,
        "phase_two_scope_accepted": not failed,
        "freeze_commit_policy": "acceptance-artifact-only",
        "production_readiness_claimed": False,
        "server_deployment_acceptance": {
            "status": "deferred_to_server_deployment",
            "gate_id": "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
            "debt_id": "NEX-DEBT-P1-13-001",
            "planned_host_type": "private_vps",
            "planned_country_code": "DE",
            "blocks": ["v0.1-production-deployment", "v0.1-release"],
            "production_readiness_claimed": False,
        },
        "security_boundary": {
            "saas": False,
            "multi_user": False,
            "public_internet_deployment": False,
            "exchange_credentials": False,
            "wallet_private_keys_or_signing": False,
            "fund_transfer": False,
            "live_order_capability": False,
            "autonomous_ai_execution": False,
            "ml_training_or_inference": False,
            "financial_advice": False,
            "tax_advice": False,
            "direct_trd_bot_database_access": False,
        },
    }
    serialized = serialize_phase_two_acceptance_record(record) + "\n"
    parse_phase_two_acceptance_record(serialized.encode())
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("x", encoding="utf-8") as output:
        output.write(serialized)
    print(f"Wrote Phase 2 final acceptance record to {arguments.output}")
    return 0 if record["ready_to_freeze_phase_two"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
