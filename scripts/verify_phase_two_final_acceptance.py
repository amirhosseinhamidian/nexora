#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-two-final-acceptance.json"
P2_11_FREEZE_PATH = ROOT / "artifacts/p2-11/transactions-holdings-reconciliation-ui-freeze.json"
CONTRACT_CHECKSUM = "84a8f2ca28020fbe52a13bba477c5a3841ca5eb5e863bf6304eebcd4eb855ae3"
P2_11_FREEZE_CHECKSUM = "e8070032a9579a0545847994e9bb0b426310f110ec6c3a0983db2a755d36be1c"
P2_11_FREEZE_COMMIT = "df6e05aa4d71a9f8b844e4c1b333449223e7dff3"
P2_11_CANDIDATE = "ef65e02e2d257b0f69277db19e96d23443b77ef2"


class PhaseTwoFinalAcceptanceContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseTwoFinalAcceptanceContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p2_11() -> None:
    path = ROOT / "scripts/verify_transactions_holdings_reconciliation_ui.py"
    spec = importlib.util.spec_from_file_location("verify_transactions_holdings_reconciliation_ui", path)
    _require(spec is not None and spec.loader is not None, "unable to load frozen P2-11 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contract = module.load_contract()
    freeze = module.load_freeze_record()
    module.validate_frozen_p2_10()
    module.validate_contract(contract)
    module.validate_runtime_markers()
    module.validate_freeze_record(freeze, contract)
    module.validate_workflow()
    _require(canonical_checksum(freeze) == P2_11_FREEZE_CHECKSUM, "P2-11 Freeze record drift")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-phase-two-final-acceptance-v1", "invalid P2-12 schema")
    _require(contract.get("decision_id") == "NEX-P2-12", "invalid P2-12 decision")
    _require(contract.get("decision_date") == "2026-11-04", "invalid P2-12 decision date")
    _require(contract.get("status") == "candidate", "P2-12 must remain candidate before acceptance")

    prerequisite = contract.get("p2_11_prerequisite")
    _require(isinstance(prerequisite, dict), "P2-11 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-11", "P2-11 decision drift")
    _require(prerequisite.get("frozen") is True, "P2-11 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_11_FREEZE_COMMIT, "P2-11 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_11_CANDIDATE,
        "P2-11 candidate drift",
    )
    _require(
        prerequisite.get("freeze_record_path") == P2_11_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-11 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_11_FREEZE_CHECKSUM, "P2-11 checksum drift")
    _require(canonical_checksum(_json(P2_11_FREEZE_PATH)) == P2_11_FREEZE_CHECKSUM, "P2-11 record drift")

    evidence = contract.get("evidence")
    _require(isinstance(evidence, dict), "evidence policy must be an object")
    _require(evidence.get("maximum_age_days") == 7, "evidence freshness drift")
    for key in (
        "same_candidate_sha_required",
        "same_environment_label_required",
        "github_actions_success_required",
        "checksums_required",
    ):
        _require(evidence.get(key) is True, f"evidence policy requires {key}")
    _require(evidence.get("capacity_report_schema") == "nexora-private-runtime-benchmark-v1", "capacity schema drift")
    _require(
        evidence.get("final_record_schema") == "nexora-phase-two-final-acceptance-record-v1",
        "acceptance record schema drift",
    )

    _require(
        contract.get("automated_gates")
        == [
            "repository_contract",
            "backend",
            "migration_cycle",
            "postgresql_accounting",
            "security_inventory",
            "frontend",
            "browser",
        ],
        "automated gate inventory drift",
    )
    database = contract.get("destructive_database_boundary")
    _require(isinstance(database, dict), "database boundary must be an object")
    _require(
        database.get("required_database_name") == "nexora_phase_two_acceptance",
        "acceptance database drift",
    )
    _require(database.get("postgresql_major") == 17, "PostgreSQL major drift")
    for key in ("production_database_allowed", "development_database_allowed", "dsn_recorded_in_artifact"):
        _require(database.get(key) is False, f"database boundary forbids {key}")

    portfolio = contract.get("portfolio_acceptance")
    _require(isinstance(portfolio, dict) and portfolio, "portfolio acceptance must be an object")
    _require(all(required is True for required in portfolio.values()), "portfolio acceptance requirement disabled")

    _require(
        contract.get("manual_evidence")
        == [
            "deterministic_accounting_fixture_review",
            "owner_scope_and_immutability_review",
            "import_reconciliation_atomicity_review",
            "projection_rebuild_and_export_review",
            "responsive_bilingual_portfolio_review",
            "no_forbidden_capabilities",
        ],
        "manual evidence inventory drift",
    )
    local = contract.get("local_reference_acceptance")
    _require(isinstance(local, dict), "local acceptance must be an object")
    _require(local.get("profile_id") == "local_reference_portfolio", "local acceptance profile drift")
    for key in (
        "actual_capacity_benchmark_required",
        "overload_429_and_retry_after_required",
        "immutable_evidence_protected",
        "https_443_only_required",
    ):
        _require(local.get(key) is True, f"local acceptance requires {key}")
    _require(local.get("non_export_api_p95_ms") == 300, "latency budget drift")
    _require(local.get("minimum_throughput_per_second") == 10, "throughput budget drift")
    _require(local.get("deployment_network_mode") == "loopback_only", "local network mode drift")
    _require(local.get("loopback_bind_address") == "127.0.0.1", "loopback bind drift")
    _require(local.get("loopback_remote_access_allowed") is False, "loopback remote access is forbidden")

    server = contract.get("server_deployment_acceptance")
    _require(isinstance(server, dict), "server deployment acceptance must be an object")
    _require(server.get("status") == "deferred_to_server_deployment", "server acceptance must remain deferred")
    _require(server.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE", "server gate drift")
    _require(server.get("debt_id") == "NEX-DEBT-P1-13-001", "server debt drift")
    _require(server.get("planned_host_type") == "private_vps", "server type drift")
    _require(server.get("planned_country_code") == "DE", "server country drift")
    _require(
        server.get("required_before") == ["v0.1-production-deployment", "v0.1-release"],
        "server release blockers drift",
    )
    _require(server.get("production_readiness_claimed") is False, "server readiness cannot be claimed")

    boundary = contract.get("acceptance_boundary")
    _require(isinstance(boundary, dict), "acceptance boundary must be an object")
    _require(boundary.get("phase_two_scope_may_be_frozen") is True, "Phase 2 Freeze is not authorized")
    for key in (
        "local_reference_acceptance_is_production_acceptance",
        "private_vps_production_readiness_claimed",
        "public_production_readiness_claimed",
    ):
        _require(boundary.get(key) is False, f"acceptance boundary forbids {key}")
    _require(boundary.get("freeze_commit_policy") == "acceptance-artifact-only", "freeze policy drift")
    _require(boundary.get("freeze_does_not_deploy_or_tag") is True, "Freeze cannot deploy or tag")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and security, "security boundary must be an object")
    for capability, enabled in security.items():
        _require(enabled is False, f"forbidden capability enabled: {capability}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_acceptance_candidate") is True, "P2-12 candidate is not ready")
    _require(transition.get("next_allowed_stage") == "NEX-P2-12-ACCEPTANCE", "next stage drift")
    _require(
        transition.get("post_freeze_stage") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
        "post-Freeze stage drift",
    )
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-12 contract checksum drift")


def validate_files_and_runtime_markers() -> None:
    required = {
        "apps/server/src/nexora/phase_two_acceptance.py": (
            "nexora-phase-two-final-acceptance-record-v1",
            "ready_to_freeze_phase_two",
            "acceptance-artifact-only",
        ),
        "scripts/run_phase_two_final_acceptance.py": (
            "nexora_phase_two_acceptance",
            "confirm-destructive-migration-cycle",
            "local_reference_portfolio",
            "postgresql_accounting",
            "security_inventory",
        ),
        "docs/v0.1/30-phase-two-final-acceptance.md": (
            "NEX-P2-12",
            "acceptance-artifact-only",
            "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
        ),
        ".github/workflows/phase-two-final-acceptance.yml": ("Phase 2 final acceptance",),
        "tests/test_phase_two_final_acceptance.py": ("PhaseTwoFinalAcceptanceContractTests",),
        "apps/server/tests/test_phase_two_acceptance.py": ("parse_phase_two_acceptance_record",),
    }
    for relative, markers in required.items():
        path = ROOT / relative
        _require(path.is_file(), f"missing P2-12 file: {relative}")
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in content, f"missing P2-12 marker in {relative}: {marker}")

    runner = (ROOT / "scripts/run_phase_two_final_acceptance.py").read_text(encoding="utf-8")
    for forbidden in ("git push", "git tag", "gh release", "docker compose down -v"):
        _require(forbidden not in runner, f"acceptance runner cannot execute {forbidden}")
    _require("nexora_production" not in runner, "acceptance runner cannot target production database")


def main() -> int:
    validate_frozen_p2_11()
    contract = load_contract()
    validate_contract(contract)
    validate_files_and_runtime_markers()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P2_11_PREREQUISITE=PASS")
    print("NEX_P2_12_FINAL_ACCEPTANCE_TOOLING=PASS")
    print("NEX_P2_12_READY_FOR_CANDIDATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
