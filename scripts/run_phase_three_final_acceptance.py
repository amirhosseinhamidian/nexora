#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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

from nexora.phase_three_acceptance import (
    P3_12_ACCEPTED_SHA,
    PROVIDER_ARTIFACT_DIGEST,
    PROVIDER_ARTIFACT_ID,
    PROVIDER_COMMIT_SHA,
    PROVIDER_PROFILE,
    PROVIDER_SOURCE_CONTRACT,
    PROVIDER_WORKFLOW_RUN_ID,
    parse_phase_three_acceptance_record,
    serialize_phase_three_acceptance_record,
)
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts/p3-13/phase-three-final-acceptance.json"
P3_12_CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-three-ui-integration.json"
P3_03_CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-durable-decision-event-projection.json"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run fail-closed Nexora Phase 3 final acceptance gates")
    value.add_argument("--database-url", default=os.environ.get("NEXORA_PHASE_THREE_ACCEPTANCE_DATABASE_URL"))
    value.add_argument(
        "--confirm-destructive-migration-cycle",
        choices=("nexora_phase_three_acceptance",),
        required=True,
    )
    value.add_argument(
        "--acceptance-profile",
        choices=("local_reference_decision_intelligence",),
        required=True,
    )
    value.add_argument("--github-actions-run-url", required=True)
    value.add_argument("--github-actions-head-sha", required=True)
    value.add_argument("--github-actions-conclusion", choices=("success",), required=True)
    for name in (
        "projection-replay-and-recovery-review",
        "owner-scope-and-immutability-review",
        "export-lineage-and-redaction-review",
        "responsive-bilingual-accessibility-review",
        "compatible-provider-smoke-review",
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
        raise ValueError("Phase 3 acceptance cannot run from detached HEAD")
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        raise ValueError("Phase 3 acceptance requires a clean worktree")
    return sha, branch


def _database_url(value: str | None) -> str:
    if not value:
        raise ValueError("--database-url or NEXORA_PHASE_THREE_ACCEPTANCE_DATABASE_URL is required")
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or url.database != "nexora_phase_three_acceptance":
        raise ValueError("destructive acceptance gates require PostgreSQL database nexora_phase_three_acceptance")
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


def _gate(
    gate_id: str,
    commands: tuple[tuple[str, tuple[str, ...]], ...],
    env: dict[str, str],
    environment_label: str,
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for label, command in commands:
        item = _command(label, command, env)
        evidence.append(item)
        if not item["passed"]:
            break
    return {
        "gate_id": gate_id,
        "environment_label": environment_label,
        "commands": evidence,
        "passed": all(item["passed"] for item in evidence),
    }


def _specs() -> tuple[tuple[str, tuple[tuple[str, tuple[str, ...]], ...]], ...]:
    python = sys.executable
    quality_paths = (
        "apps/server",
        "alembic",
        "scripts/run_phase_three_final_acceptance.py",
        "scripts/verify_phase_three_final_acceptance.py",
        "tests/test_phase_three_final_acceptance.py",
    )
    chain = tuple(
        (label, (python, path))
        for label, path in (
            ("P3-00 roadmap Freeze", "scripts/verify_phase_three_roadmap.py"),
            ("P3-01 domain Freeze", "scripts/verify_decision_review_journal_domain.py"),
            ("P3-02 integration contract Freeze", "scripts/verify_trd_bot_v031_integration_contract.py"),
            ("P3-03 durable projection", "scripts/verify_durable_decision_event_projection.py"),
            ("P3-04 Decision feed", "scripts/verify_decision_feed_candidate_details.py"),
            ("P3-05 Risk Gate", "scripts/verify_risk_gate_explanation.py"),
            ("P3-06 Portfolio impact", "scripts/verify_portfolio_candidate_impact.py"),
            ("P3-07 human review", "scripts/verify_human_decision_review.py"),
            ("P3-08 Alert Inbox", "scripts/verify_alert_inbox.py"),
            ("P3-09 watchlists", "scripts/verify_watchlists.py"),
            ("P3-10 Outcome Journal", "scripts/verify_outcome_journal.py"),
            ("P3-11 export coverage", "scripts/verify_phase_three_export_coverage.py"),
            ("P3-12 UI integration", "scripts/verify_phase_three_ui_integration.py"),
        )
    )
    return (
        (
            "repository_contract",
            (
                ("P3-13 contract verifier", (python, "scripts/verify_phase_three_final_acceptance.py")),
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
                ("Runtime contract drift", (python, "scripts/generate_runtime_contracts.py", "--check")),
            ),
        ),
        (
            "migration_cycle",
            (
                ("Alembic upgrade from zero", (python, "-m", "alembic", "upgrade", "head")),
                ("Alembic downgrade", (python, "-m", "alembic", "downgrade", "base")),
                ("Alembic rebuild", (python, "-m", "alembic", "upgrade", "head")),
                ("Alembic drift", (python, "-m", "alembic", "check")),
            ),
        ),
        (
            "postgresql_projection_recovery",
            (("PostgreSQL projection and recovery", (python, "-m", "pytest", "-m", "integration", "-q")),),
        ),
        ("phase_three_contract_chain", chain),
        (
            "security_inventory",
            (
                ("Scope boundary", (python, "scripts/verify_scope_contract.py")),
                ("Security boundary", (python, "scripts/verify_security_boundary.py")),
                ("Integration contracts", (python, "scripts/verify_integration_contracts.py")),
            ),
        ),
        (
            "export_coverage",
            (
                ("Phase 3 export contract", (python, "scripts/verify_phase_three_export_coverage.py")),
                (
                    "Phase 3 export regression",
                    (python, "-m", "pytest", "apps/server/tests/test_portfolio_export.py", "-q"),
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
        ("browser", (("Phase 3 browser acceptance", ("pnpm", "--filter", "@nexora/web", "test:e2e")),)),
        (
            "provider_smoke_evidence",
            (("Compatible provider smoke evidence", (python, "scripts/verify_durable_decision_event_projection.py")),),
        ),
    )


def _canonical_checksum(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _prior_stage() -> dict[str, Any]:
    if _git("merge-base", "--is-ancestor", P3_12_ACCEPTED_SHA, "HEAD", check=False).returncode != 0:
        raise ValueError("P3-12 accepted commit is not an ancestor of the candidate")
    contract = json.loads(P3_12_CONTRACT_PATH.read_text(encoding="utf-8"))
    if contract.get("decision_id") != "NEX-P3-12":
        raise ValueError("P3-12 contract drift")
    transition = contract.get("transition")
    if not isinstance(transition, dict) or transition.get("next_allowed_stage_after_ci_acceptance") != "NEX-P3-13":
        raise ValueError("P3-12 does not open P3-13")
    return {
        "decision_id": "NEX-P3-12",
        "accepted_commit_sha": P3_12_ACCEPTED_SHA,
        "contract_checksum": _canonical_checksum(P3_12_CONTRACT_PATH),
        "same_sha_ci_accepted": True,
    }


def _provider_smoke() -> dict[str, Any]:
    contract = json.loads(P3_03_CONTRACT_PATH.read_text(encoding="utf-8"))
    prerequisite = contract.get("prerequisites")
    if not isinstance(prerequisite, dict):
        raise ValueError("P3-03 provider smoke evidence is missing")
    expected = {
        "provider_release": "0.3.1",
        "provider_commit_sha": PROVIDER_COMMIT_SHA,
        "workflow_run_id": PROVIDER_WORKFLOW_RUN_ID,
        "artifact_id": PROVIDER_ARTIFACT_ID,
        "artifact_digest": PROVIDER_ARTIFACT_DIGEST,
        "provider_profile": PROVIDER_PROFILE,
        "bound_by_contract": PROVIDER_SOURCE_CONTRACT,
        "real_local_smoke_passed": True,
    }
    if prerequisite.get("trd_bot_release") != expected["provider_release"]:
        raise ValueError("provider release drift")
    if prerequisite.get("trd_bot_release_commit_sha") != expected["provider_commit_sha"]:
        raise ValueError("provider commit drift")
    if prerequisite.get("trd_bot_release_workflow_run_id") != expected["workflow_run_id"]:
        raise ValueError("provider workflow drift")
    if prerequisite.get("real_local_provider_smoke_artifact_id") != expected["artifact_id"]:
        raise ValueError("provider smoke artifact drift")
    if prerequisite.get("real_local_provider_smoke_digest") != expected["artifact_digest"]:
        raise ValueError("provider smoke digest drift")
    if prerequisite.get("provider_profile") != expected["provider_profile"]:
        raise ValueError("provider profile drift")
    return expected


def main() -> int:
    arguments = parser().parse_args()
    if arguments.output.exists():
        raise FileExistsError("Phase 3 acceptance output already exists")
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

    prior_stage = _prior_stage()
    provider_smoke = _provider_smoke()
    clean_environment = {key: value for key, value in os.environ.items() if not key.startswith("NEXORA_")}
    with tempfile.TemporaryDirectory(prefix="nexora-phase-three-acceptance-") as temporary:
        dsn_path = Path(temporary) / "database.dsn"
        dsn_path.write_text(database_url + "\n", encoding="utf-8")
        dsn_path.chmod(0o600)
        clean_environment["NEXORA_MIGRATION_DATABASE_DSN_FILE"] = str(dsn_path)
        gates = tuple(
            _gate(gate_id, commands, clean_environment, arguments.environment_label) for gate_id, commands in _specs()
        )
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        raise ValueError("acceptance gates changed the candidate worktree")

    failed = [gate["gate_id"] for gate in gates if not gate["passed"]]
    manual = {
        "projection_replay_and_recovery_review": arguments.projection_replay_and_recovery_review,
        "owner_scope_and_immutability_review": arguments.owner_scope_and_immutability_review,
        "export_lineage_and_redaction_review": arguments.export_lineage_and_redaction_review,
        "responsive_bilingual_accessibility_review": arguments.responsive_bilingual_accessibility_review,
        "compatible_provider_smoke_review": arguments.compatible_provider_smoke_review,
        "no_forbidden_capabilities": arguments.no_forbidden_capabilities,
    }
    record: dict[str, Any] = {
        "schema_version": "nexora-phase-three-final-acceptance-record-v1",
        "candidate_commit_sha": candidate_sha,
        "branch": branch,
        "acceptance_profile": arguments.acceptance_profile,
        "environment_label": arguments.environment_label,
        "generated_at": datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "prior_stage": prior_stage,
        "provider_smoke": provider_smoke,
        "ci": {
            "run_url": arguments.github_actions_run_url,
            "head_sha": ci_sha,
            "conclusion": arguments.github_actions_conclusion,
        },
        "manual": manual,
        "gates": list(gates),
        "failed_gates": failed,
        "ready_to_freeze_phase_three": not failed,
        "phase_three_scope_accepted": not failed,
        "freeze_commit_policy": "acceptance-artifact-only",
        "production_readiness_claimed": False,
        "server_deployment_acceptance": {
            "status": "deferred_until_private_vps_available",
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
    serialized = serialize_phase_three_acceptance_record(record) + "\n"
    parse_phase_three_acceptance_record(serialized.encode())
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("x", encoding="utf-8") as output:
        output.write(serialized)
    print(f"Wrote Phase 3 final acceptance record to {arguments.output}")
    return 0 if record["ready_to_freeze_phase_three"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
