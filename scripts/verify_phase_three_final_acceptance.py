#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-three-final-acceptance.json"
P3_12_CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-three-ui-integration.json"
P3_03_CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-durable-decision-event-projection.json"
P3_12_ACCEPTED_SHA = "7fb3a707dc6b3c059eb2e65b06490385f18c3b1b"
PROVIDER_COMMIT_SHA = "3097276ed77cd212101797654452456b7fbc61de"
PROVIDER_ARTIFACT_DIGEST = "sha256:d1ec79aa429891ae94a36a4d65d573c3b97550ceaffa343b3df8989286d3375d"
CONTRACT_CHECKSUM = "f31d04e88acf2430ee8336245d57fbb867c1c168634225a057c15f4ad61f81a7"

EXPECTED_GATES = [
    "repository_contract",
    "backend",
    "migration_cycle",
    "postgresql_projection_recovery",
    "phase_three_contract_chain",
    "security_inventory",
    "export_coverage",
    "frontend",
    "browser",
    "provider_smoke_evidence",
]
EXPECTED_MANUAL = [
    "projection_replay_and_recovery_review",
    "owner_scope_and_immutability_review",
    "export_lineage_and_redaction_review",
    "responsive_bilingual_accessibility_review",
    "compatible_provider_smoke_review",
    "no_forbidden_capabilities",
]
PHASE_THREE_VERIFIERS = (
    ("verify_phase_three_roadmap.py", "main"),
    ("verify_decision_review_journal_domain.py", "main"),
    ("verify_trd_bot_v031_integration_contract.py", "main"),
    ("verify_durable_decision_event_projection.py", "verify"),
    ("verify_decision_feed_candidate_details.py", "verify"),
    ("verify_risk_gate_explanation.py", "verify"),
    ("verify_portfolio_candidate_impact.py", "verify"),
    ("verify_human_decision_review.py", "verify"),
    ("verify_alert_inbox.py", "verify"),
    ("verify_watchlists.py", "verify"),
    ("verify_outcome_journal.py", "verify"),
    ("verify_phase_three_export_coverage.py", "verify"),
    ("verify_phase_three_ui_integration.py", "verify"),
)


class PhaseThreeFinalAcceptanceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseThreeFinalAcceptanceError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def canonical_checksum(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_phase_three_chain() -> None:
    for verifier, entrypoint in PHASE_THREE_VERIFIERS:
        path = ROOT / "scripts" / verifier
        spec = importlib.util.spec_from_file_location(f"p3_13_{path.stem}", path)
        require(spec is not None and spec.loader is not None, f"unable to load Phase 3 verifier: {verifier}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        validate = getattr(module, entrypoint, None)
        require(callable(validate), f"Phase 3 verifier has no {entrypoint} function: {verifier}")
        result = validate()
        require(result in (None, 0), f"Phase 3 verifier failed: {verifier}")


def validate_p3_12_prerequisite() -> None:
    prerequisite = load_json(P3_12_CONTRACT_PATH)
    require(prerequisite.get("decision_id") == "NEX-P3-12", "P3-12 decision drift")
    require(
        prerequisite.get("schema_version") == "nexora-phase-three-ui-integration-v1",
        "P3-12 schema drift",
    )
    transition = prerequisite.get("transition")
    require(isinstance(transition, dict), "P3-12 transition missing")
    require(
        transition.get("next_allowed_stage_after_ci_acceptance") == "NEX-P3-13",
        "P3-12 does not open P3-13",
    )
    require(transition.get("production_readiness_claimed") is False, "P3-12 production claim drift")


def validate_provider_smoke_source() -> None:
    source = load_json(P3_03_CONTRACT_PATH)
    prerequisite = source.get("prerequisites")
    require(isinstance(prerequisite, dict), "P3-03 provider prerequisite missing")
    require(prerequisite.get("trd_bot_release") == "0.3.1", "provider release drift")
    require(prerequisite.get("trd_bot_release_commit_sha") == PROVIDER_COMMIT_SHA, "provider commit drift")
    require(prerequisite.get("real_local_provider_smoke_artifact_id") == 13939958030, "provider artifact drift")
    require(
        prerequisite.get("real_local_provider_smoke_digest") == PROVIDER_ARTIFACT_DIGEST,
        "provider smoke digest drift",
    )


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("schema_version") == "nexora-phase-three-final-acceptance-v1", "schema drift")
    require(contract.get("decision_id") == "NEX-P3-13", "stage ID drift")
    require(contract.get("decision_date") == "2026-11-18", "decision date drift")
    require(contract.get("status") == "candidate", "P3-13 must remain candidate before acceptance")

    prerequisite = contract.get("p3_12_prerequisite")
    require(isinstance(prerequisite, dict), "P3-12 prerequisite missing")
    require(prerequisite.get("decision_id") == "NEX-P3-12", "P3-12 decision drift")
    require(prerequisite.get("accepted_commit_sha") == P3_12_ACCEPTED_SHA, "P3-12 accepted SHA drift")
    require(
        prerequisite.get("contract_path") == P3_12_CONTRACT_PATH.relative_to(ROOT).as_posix(),
        "P3-12 contract path drift",
    )
    require(prerequisite.get("same_sha_ci_accepted") is True, "P3-12 CI acceptance missing")
    require(prerequisite.get("opens_stage") == "NEX-P3-13", "P3-12 transition drift")

    evidence = contract.get("evidence")
    require(isinstance(evidence, dict), "evidence policy missing")
    for key in (
        "same_candidate_sha_required",
        "same_environment_label_required",
        "github_actions_success_required",
        "checksums_required",
    ):
        require(evidence.get(key) is True, f"evidence policy requires {key}")
    require(
        evidence.get("final_record_schema") == "nexora-phase-three-final-acceptance-record-v1",
        "final record schema drift",
    )

    require(contract.get("automated_gates") == EXPECTED_GATES, "automated gate inventory drift")
    database = contract.get("destructive_database_boundary")
    require(isinstance(database, dict), "database boundary missing")
    require(database.get("required_database_name") == "nexora_phase_three_acceptance", "database name drift")
    require(database.get("postgresql_major") == 17, "PostgreSQL major drift")
    for key in ("production_database_allowed", "development_database_allowed", "dsn_recorded_in_artifact"):
        require(database.get(key) is False, f"database boundary forbids {key}")

    acceptance = contract.get("phase_three_acceptance")
    require(isinstance(acceptance, dict) and acceptance, "Phase 3 acceptance requirements missing")
    require(all(value is True for value in acceptance.values()), "Phase 3 acceptance requirement disabled")

    provider = contract.get("provider_smoke_evidence")
    require(isinstance(provider, dict), "provider smoke evidence missing")
    require(provider.get("provider_release") == "0.3.1", "provider release drift")
    require(provider.get("provider_commit_sha") == PROVIDER_COMMIT_SHA, "provider commit drift")
    require(provider.get("workflow_run_id") == 43210235551, "provider workflow drift")
    require(provider.get("artifact_id") == 13939958030, "provider artifact drift")
    require(provider.get("artifact_digest") == PROVIDER_ARTIFACT_DIGEST, "provider digest drift")
    require(
        provider.get("provider_profile") == "contracts/integration/v1/trd-bot-v0.3.1-provider-profile.json",
        "provider profile drift",
    )
    require(
        provider.get("bound_by_contract") == P3_03_CONTRACT_PATH.relative_to(ROOT).as_posix(),
        "provider source contract drift",
    )
    require(provider.get("real_local_smoke_passed") is True, "provider smoke is not accepted")

    require(contract.get("manual_evidence") == EXPECTED_MANUAL, "manual evidence inventory drift")
    server = contract.get("server_deployment_acceptance")
    require(isinstance(server, dict), "server deployment acceptance missing")
    require(
        server.get("status") == "deferred_until_private_vps_available",
        "server acceptance must remain deferred",
    )
    require(server.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE", "server gate drift")
    require(server.get("debt_id") == "NEX-DEBT-P1-13-001", "server debt drift")
    require(server.get("planned_host_type") == "private_vps", "server host drift")
    require(server.get("planned_country_code") == "DE", "server country drift")
    require(
        server.get("required_before") == ["v0.1-production-deployment", "v0.1-release"],
        "server release blockers drift",
    )
    require(server.get("production_readiness_claimed") is False, "server readiness claimed")

    boundary = contract.get("acceptance_boundary")
    require(isinstance(boundary, dict), "acceptance boundary missing")
    require(boundary.get("phase_three_scope_may_be_frozen") is True, "Phase 3 Freeze is not authorized")
    for key in (
        "local_acceptance_is_production_acceptance",
        "private_vps_production_readiness_claimed",
        "public_production_readiness_claimed",
    ):
        require(boundary.get(key) is False, f"acceptance boundary forbids {key}")
    require(boundary.get("freeze_commit_policy") == "acceptance-artifact-only", "freeze policy drift")
    require(boundary.get("freeze_does_not_deploy_or_tag") is True, "Freeze cannot deploy or tag")

    security = contract.get("security_boundary")
    require(isinstance(security, dict) and security, "security boundary missing")
    require(not any(security.values()), "security boundary widened")

    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition missing")
    require(transition.get("ready_for_acceptance_candidate") is True, "P3-13 candidate is not ready")
    require(transition.get("next_allowed_stage") == "NEX-P3-13-ACCEPTANCE", "next stage drift")
    require(transition.get("phase_three_complete_after_freeze") is True, "Phase 3 completion drift")
    require(
        transition.get("post_freeze_stage") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
        "post-Freeze stage drift",
    )
    require(transition.get("production_readiness_claimed") is False, "production readiness claimed")
    require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P3-13 contract checksum drift")


def validate_files_and_workflow() -> None:
    required = {
        "apps/server/src/nexora/phase_three_acceptance.py": (
            "nexora-phase-three-final-acceptance-record-v1",
            "ready_to_freeze_phase_three",
            "acceptance-artifact-only",
        ),
        "scripts/run_phase_three_final_acceptance.py": (
            "nexora_phase_three_acceptance",
            "confirm-destructive-migration-cycle",
            "provider_smoke_evidence",
        ),
        "docs/v0.1/46-phase-three-final-acceptance.md": (
            "NEX-P3-13",
            "acceptance-artifact-only",
            "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
        ),
        ".github/workflows/phase-three-final-acceptance.yml": ("Phase 3 final acceptance",),
        "tests/test_phase_three_final_acceptance.py": ("PhaseThreeFinalAcceptanceContractTests",),
        "apps/server/tests/test_phase_three_acceptance.py": ("parse_phase_three_acceptance_record",),
    }
    for relative, markers in required.items():
        path = ROOT / relative
        require(path.is_file(), f"missing P3-13 file: {relative}")
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            require(marker in content, f"missing P3-13 marker in {relative}: {marker}")

    runner = (ROOT / "scripts/run_phase_three_final_acceptance.py").read_text(encoding="utf-8")
    for forbidden in ("git push", "git tag", "gh release", "docker compose down -v"):
        require(forbidden not in runner, f"acceptance runner cannot execute {forbidden}")
    require("nexora_production" not in runner, "acceptance runner cannot target production database")

    workflow = (ROOT / ".github/workflows/phase-three-final-acceptance.yml").read_text(encoding="utf-8")
    for marker in (
        "python3 scripts/verify_phase_three_ui_integration.py",
        "python3 scripts/verify_phase_three_final_acceptance.py",
        "python3 -m unittest discover -s tests -v",
        "uv run ruff format --check",
        "uv run ruff check",
        "uv run mypy",
        'uv run pytest -m "not integration" -q',
        "uv run alembic upgrade head",
        "uv run pytest -m integration -q",
        "uv run alembic downgrade base",
        "uv run alembic check",
        "python3 scripts/verify_security_boundary.py",
        "python3 scripts/verify_phase_three_export_coverage.py",
        "pnpm format:check",
        "pnpm lint",
        "pnpm typecheck",
        "pnpm test",
        "pnpm build",
        "playwright install --with-deps chromium",
        "pnpm --filter @nexora/web test:e2e",
    ):
        require(marker in workflow, f"P3-13 workflow marker missing: {marker}")


def verify() -> None:
    validate_phase_three_chain()
    validate_p3_12_prerequisite()
    validate_provider_smoke_source()
    validate_contract(load_contract())
    validate_files_and_workflow()


def main() -> int:
    verify()
    print("NEX_P3_12_ACCEPTED_SHA=PASS")
    print("NEX_P3_13_FINAL_ACCEPTANCE_TOOLING=PASS")
    print("NEX_P3_13_PROVIDER_SMOKE_EVIDENCE=BOUND")
    print("NEX_P3_13_READY_FOR_ACCEPTANCE_CANDIDATE=PASS")
    print("NEX_V0_1_SERVER_DEPLOYMENT_GATE=PRESERVED_DEFERRED")
    print("PRODUCTION_READINESS_CLAIMED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
