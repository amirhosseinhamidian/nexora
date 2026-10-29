#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-one-final-acceptance.json"
P1_12_FREEZE_PATH = ROOT / "artifacts/p1-12/private-deployment-operations-freeze.json"
CONTRACT_CHECKSUM = "1a764ba49ce6526233b6000259f3a8f4bdfad7f1d963c93c6d87b68135715332"
P1_12_FREEZE_CHECKSUM = "49d9c3c2427d4154445a25c61be8945dca4b46cbcfe43ce25e538c37a457cda6"
P1_12_FREEZE_COMMIT = "1af9161925a71c4154801bb6ac4f533f4a8e21b8"


class PhaseOneFinalAcceptanceContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseOneFinalAcceptanceContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p1_12() -> None:
    path = ROOT / "scripts/verify_private_deployment_operations.py"
    spec = importlib.util.spec_from_file_location("verify_private_deployment_operations", path)
    if spec is None or spec.loader is None:
        raise PhaseOneFinalAcceptanceContractError("unable to load frozen P1-12 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_p1_11()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_files_and_runtime_markers()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-phase-one-final-acceptance-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P1-13", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-28", "invalid decision date")
    _require(contract.get("status") == "candidate", "P1-13 must remain candidate")

    prerequisite = contract.get("p1_12_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-12 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-12", "P1-12 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P1-12 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P1_12_FREEZE_COMMIT, "P1-12 commit drift")
    _require(
        prerequisite.get("freeze_record_path") == "artifacts/p1-12/private-deployment-operations-freeze.json",
        "P1-12 path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P1_12_FREEZE_CHECKSUM, "P1-12 checksum drift")
    _require(canonical_checksum(_json(P1_12_FREEZE_PATH)) == P1_12_FREEZE_CHECKSUM, "P1-12 record drift")
    _require(contract.get("closes_gaps") == ["NEX-P1-GAP-009"], "P1-13 gap ownership drift")
    _require(
        contract.get("opens_deferred_debts") == ["NEX-DEBT-P1-13-001"],
        "server deployment debt ownership drift",
    )

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
        evidence.get("final_record_schema") == "nexora-phase-one-final-acceptance-record-v1",
        "acceptance record schema drift",
    )

    _require(
        contract.get("automated_gates")
        == [
            "repository_contract",
            "backend",
            "migration_cycle",
            "postgresql_resilience",
            "frontend",
            "browser",
        ],
        "automated gate inventory drift",
    )
    database = contract.get("destructive_database_boundary")
    _require(isinstance(database, dict), "database boundary must be an object")
    _require(database.get("required_database_name") == "nexora_acceptance", "acceptance database drift")
    for key in ("production_database_allowed", "development_database_allowed", "dsn_recorded_in_artifact"):
        _require(database.get(key) is False, f"database boundary forbids {key}")

    _require(
        contract.get("manual_evidence")
        == [
            "fresh_clone_install",
            "passkey_session_and_csrf_lifecycle",
            "trd_bot_contract_and_idempotency",
            "responsive_bilingual_web_shell",
            "no_forbidden_capabilities",
        ],
        "manual evidence inventory drift",
    )
    local = contract.get("local_reference_acceptance")
    _require(isinstance(local, dict), "local reference acceptance must be an object")
    _require(local.get("profile_id") == "local_reference_foundation", "local acceptance profile drift")
    for key in (
        "actual_capacity_benchmark_required",
        "overload_429_and_retry_after_required",
        "immutable_evidence_protected",
        "worker_restart_and_reclaim_required",
        "https_443_only_required",
    ):
        _require(local.get(key) is True, f"local acceptance requires {key}")
    _require(local.get("non_export_api_p95_ms") == 300, "latency budget drift")
    _require(local.get("minimum_throughput_per_second") == 10, "throughput budget drift")
    _require(local.get("deployment_network_mode") == "loopback_only", "local network mode drift")
    _require(local.get("loopback_bind_address") == "127.0.0.1", "loopback bind address drift")
    _require(local.get("loopback_remote_access_allowed") is False, "loopback remote access is forbidden")

    server = contract.get("server_deployment_acceptance")
    _require(isinstance(server, dict), "server deployment acceptance must be an object")
    _require(server.get("status") == "deferred_to_server_deployment", "server acceptance must remain deferred")
    _require(server.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE", "server gate drift")
    _require(server.get("debt_id") == "NEX-DEBT-P1-13-001", "server deployment debt drift")
    _require(server.get("planned_host_type") == "private_vps", "planned server type drift")
    _require(server.get("planned_country_code") == "DE", "planned server country drift")
    _require(
        server.get("required_before") == ["v0.1-production-deployment", "v0.1-release"],
        "server acceptance release blockers drift",
    )
    _require(
        server.get("required_evidence")
        == [
            "authenticated_private_network_or_equivalent_hardened_access",
            "encrypted_runtime_backup",
            "independent_off_host_backup_copy",
            "restore_drill_within_rto",
            "retention_dry_run",
            "server_capacity_and_overload_benchmark",
            "worker_restart_and_reclaim",
            "post_restore_session_and_service_token_revocation",
        ],
        "server acceptance evidence inventory drift",
    )
    _require(
        server.get("operations_drill_report_schema") == "nexora-private-operations-drill-v1",
        "server operations drill schema drift",
    )
    _require(server.get("restore_rto_hours") == 4, "server restore RTO drift")
    _require(server.get("runtime_copy_counts_as_off_host") is False, "runtime copy cannot count as off-host")
    _require(server.get("production_readiness_claimed") is False, "server readiness cannot be claimed locally")

    provider = contract.get("trd_bot_provider_acceptance")
    _require(isinstance(provider, dict), "TRD Bot provider acceptance must be an object")
    _require(
        provider.get("default_runtime_mode") == "disabled_incompatible_provider",
        "TRD Bot default runtime mode drift",
    )
    _require(provider.get("provider_0_3_0_sync_allowed") is False, "TRD Bot 0.3.0 sync is forbidden")
    _require(provider.get("live_provider_smoke_required") is False, "live provider smoke cannot be claimed")
    _require(
        provider.get("contract_and_idempotency_tests_required") is True,
        "TRD Bot contract tests are required",
    )
    _require(provider.get("compatible_provider_range") == ">=0.3.1,<0.4.0", "provider range drift")
    _require(
        provider.get("capability_negotiation_required_before_enable") is True,
        "provider negotiation is required",
    )
    _require(provider.get("credentials_required_when_disabled") is False, "disabled provider cannot require secrets")

    boundary = contract.get("acceptance_boundary")
    _require(isinstance(boundary, dict), "acceptance boundary must be an object")
    _require(boundary.get("phase_one_foundation_may_be_frozen") is True, "Phase 1 freeze is not authorized")
    _require(
        boundary.get("local_reference_acceptance_is_production_acceptance") is False,
        "local acceptance cannot become production acceptance",
    )
    _require(
        boundary.get("private_vps_production_readiness_claimed") is False,
        "private VPS readiness cannot be claimed",
    )
    _require(boundary.get("portfolio_product_complete") is False, "Portfolio product cannot be complete in Phase 1")
    _require(boundary.get("public_production_readiness_claimed") is False, "public readiness cannot be claimed")
    _require(boundary.get("freeze_commit_policy") == "acceptance-artifact-only", "freeze policy drift")
    _require(boundary.get("freeze_does_not_deploy_or_tag") is True, "freeze cannot deploy or tag")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and security, "security boundary must be an object")
    for capability, enabled in security.items():
        _require(enabled is False, f"forbidden capability enabled: {capability}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_acceptance_candidate") is True, "P1-13 candidate is not ready")
    _require(transition.get("next_allowed_stage") == "NEX-P1-13-ACCEPTANCE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P2-01", "post-freeze stage drift")
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "Phase 1 final acceptance contract drift")


def validate_files_and_runtime_markers() -> None:
    required = {
        "apps/server/src/nexora/phase_one_acceptance.py": (
            "PHASE_ONE_MAX_EVIDENCE_AGE",
            "acceptance-artifact-only",
            "ready_to_freeze_phase_one",
        ),
        "scripts/benchmark_private_runtime.py": (
            "environment_label",
            "generated_at",
            "deployment_network_mode",
            'BENCHMARK_PATH = "/api/v1/auth/session"',
        ),
        "scripts/record_private_operations_drill.py": (
            "nexora-private-operations-drill-v1",
            "service_token_rotation_completed",
            "runtime_and_offsite_copies_match",
            "loopback_only",
        ),
        "scripts/run_phase_one_final_acceptance.py": (
            "nexora_acceptance",
            "confirm-destructive-migration-cycle",
            "local_reference_foundation",
            "deferred_to_server_deployment",
            "acceptance-artifact-only",
            "disabled_incompatible_provider",
        ),
        "infra/compose/private-single-host.yml": ("NEXORA_TRD_BOT_MODE: disabled_incompatible_provider",),
        "infra/compose/private-single-host.trd-bot.yml": (
            "enabled_compatible_provider",
            "NEXORA_TRD_BOT_BASE_URL_FILE",
            "NEXORA_TRD_BOT_TOKEN_FILE",
        ),
        "docs/adr/0027-phase-one-final-acceptance.md": (
            "Status: Candidate for NEX-P1-13",
            "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
        ),
        "docs/v0.1/18-phase-one-final-acceptance.md": (
            "NEX-P1-GAP-009",
            "acceptance-artifact-only",
            "NEX-P2-01",
            "loopback-only",
            "VPS آلمان",
        ),
        ".github/workflows/phase-one-final-acceptance.yml": ("Phase 1 final acceptance",),
        "tests/test_phase_one_final_acceptance.py": ("PhaseOneFinalAcceptanceContractTests",),
        "apps/server/tests/test_phase_one_acceptance.py": ("parse_phase_one_acceptance_record",),
    }
    for relative, markers in required.items():
        path = ROOT / relative
        _require(path.is_file(), f"missing P1-13 file: {relative}")
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in content, f"missing P1-13 marker in {relative}: {marker}")

    runner = (ROOT / "scripts/run_phase_one_final_acceptance.py").read_text(encoding="utf-8")
    for forbidden in ("git push", "git tag", "gh release", "docker compose down -v"):
        _require(forbidden not in runner, f"acceptance runner cannot execute {forbidden}")
    _require("nexora_production" not in runner, "acceptance runner cannot target production database")


def main() -> int:
    validate_frozen_p1_12()
    contract = load_contract()
    validate_contract(contract)
    validate_files_and_runtime_markers()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_12_PREREQUISITE=PASS")
    print("NEX_P1_13_FINAL_ACCEPTANCE_TOOLING=PASS")
    print("NEX_P1_13_READY_FOR_CANDIDATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
