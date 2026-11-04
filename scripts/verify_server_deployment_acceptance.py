#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-server-deployment-acceptance.json"
P2_12_RECORD_PATH = ROOT / "artifacts/p2-12/phase-two-final-acceptance.json"
CONTRACT_CHECKSUM = "7f80d36b857fe1921d25c0fd78f2b394c0a61d93868b761390e6930f710288ad"
P2_12_RECORD_CHECKSUM = "114a660b358ba58e16cc3f2b885c20cc72d0b20e0d425f5c266dd2120c0daedb"
P2_12_FREEZE_COMMIT = "ffe5b1b50c6eb7b09bfe052ad96038de47b779df"


class ServerDeploymentAcceptanceContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ServerDeploymentAcceptanceContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_p2_12_prerequisite() -> None:
    record = _json(P2_12_RECORD_PATH)
    checksum = record.get("record_checksum")
    unsigned = dict(record)
    unsigned.pop("record_checksum", None)
    _require(checksum == P2_12_RECORD_CHECKSUM, "P2-12 record checksum field drift")
    _require(
        canonical_checksum(unsigned) == P2_12_RECORD_CHECKSUM,
        "P2-12 record checksum mismatch",
    )
    _require(record.get("ready_to_freeze_phase_two") is True, "P2-12 is not ready")
    _require(record.get("phase_two_scope_accepted") is True, "Phase 2 scope was not accepted")
    _require(
        record.get("production_readiness_claimed") is False,
        "P2-12 overclaims readiness",
    )
    deferred = record.get("server_deployment_acceptance")
    _require(isinstance(deferred, dict), "P2-12 server acceptance debt is missing")
    _require(deferred.get("debt_id") == "NEX-DEBT-P1-13-001", "server acceptance debt drift")
    _require(
        deferred.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
        "server gate drift",
    )
    _require(
        deferred.get("status") == "deferred_to_server_deployment",
        "server gate is not deferred",
    )


def validate_contract(contract: dict[str, Any]) -> None:
    _require(
        contract.get("schema_version") == "nexora-server-deployment-acceptance-v1",
        "invalid schema",
    )
    _require(
        contract.get("decision_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
        "invalid decision ID",
    )
    _require(contract.get("decision_date") == "2026-11-04", "decision date drift")
    _require(contract.get("status") == "candidate", "server acceptance must remain candidate")
    prerequisite = contract.get("p2_12_prerequisite")
    _require(isinstance(prerequisite, dict), "P2-12 prerequisite must be an object")
    _require(prerequisite.get("frozen") is True, "P2-12 prerequisite is not frozen")
    _require(
        prerequisite.get("freeze_commit_sha") == P2_12_FREEZE_COMMIT,
        "P2-12 Freeze commit drift",
    )
    _require(
        prerequisite.get("acceptance_record_checksum") == P2_12_RECORD_CHECKSUM,
        "P2-12 checksum drift",
    )
    _require(contract.get("closes_debts") == ["NEX-DEBT-P1-13-001"], "debt ownership drift")

    deployment = contract.get("deployment")
    _require(isinstance(deployment, dict), "deployment must be an object")
    _require(deployment.get("host_type") == "private_vps", "host type drift")
    _require(deployment.get("country_code") == "DE", "host country drift")
    _require(
        deployment.get("profile") == "private_single_owner_v0.1",
        "deployment profile drift",
    )
    _require(
        deployment.get("network_mode") == "authenticated_private_overlay",
        "network mode drift",
    )
    _require(
        deployment.get("public_network_exposure") is False,
        "public exposure is forbidden",
    )
    _require(
        deployment.get("only_application_host_port") == 443,
        "only application HTTPS 443 is allowed",
    )
    _require(deployment.get("tls_minimum") == "1.3", "TLS minimum drift")

    evidence = contract.get("evidence")
    _require(isinstance(evidence, dict), "evidence must be an object")
    _require(evidence.get("maximum_age_days") == 7, "evidence age drift")
    for key in (
        "same_candidate_sha_required",
        "same_environment_label_required",
        "github_actions_success_required",
        "checksums_required",
    ):
        _require(evidence.get(key) is True, f"evidence requires {key}")
    _require(
        evidence.get("operations_drill_schema") == "nexora-private-operations-drill-v1",
        "drill schema drift",
    )
    _require(
        evidence.get("capacity_report_schema") == "nexora-private-runtime-benchmark-v1",
        "capacity schema drift",
    )
    _require(
        evidence.get("final_record_schema") == "nexora-server-deployment-acceptance-record-v1",
        "record schema drift",
    )

    required = contract.get("required_evidence")
    _require(
        isinstance(required, list) and len(required) == 8 and len(set(required)) == 8,
        "required evidence drift",
    )
    backup = contract.get("backup_and_restore")
    _require(isinstance(backup, dict), "backup and restore must be an object")
    _require(
        backup.get("runtime_copy_counts_as_off_host") is False,
        "runtime copy cannot count as off-host",
    )
    _require(
        backup.get("minimum_independent_off_host_copies") == 1,
        "off-host copy requirement drift",
    )
    _require(backup.get("recovery_point_objective_hours") == 24, "RPO drift")
    _require(backup.get("recovery_time_objective_hours") == 4, "RTO drift")
    for key in (
        "sessions_revoked_after_restore",
        "service_tokens_revoked_after_restore",
        "service_token_rotation_required",
    ):
        _require(backup.get(key) is True, f"restore requires {key}")

    capacity = contract.get("capacity_and_overload")
    _require(isinstance(capacity, dict), "capacity must be an object")
    _require(capacity.get("minimum_completed_samples") == 1000, "sample budget drift")
    _require(capacity.get("minimum_throughput_per_second") == 10, "throughput budget drift")
    _require(capacity.get("latency_p95_budget_ms") == 300, "latency budget drift")
    for key in ("http_429_required", "retry_after_required_on_all_429"):
        _require(capacity.get(key) is True, f"capacity requires {key}")
    for key in ("transport_or_5xx_failures_allowed", "immutable_evidence_dropped"):
        _require(capacity.get(key) is False, f"capacity forbids {key}")

    boundary = contract.get("acceptance_boundary")
    _require(isinstance(boundary, dict), "acceptance boundary must be an object")
    _require(
        boundary.get("private_v0_1_release_may_be_unblocked") is True,
        "private release transition drift",
    )
    _require(
        boundary.get("production_readiness_scope") == "private_single_owner_v0.1",
        "readiness scope drift",
    )
    _require(
        boundary.get("public_internet_production_readiness_claimed") is False,
        "public readiness is forbidden",
    )
    _require(boundary.get("high_availability_claimed") is False, "HA claim is forbidden")
    _require(
        boundary.get("freeze_commit_policy") == "acceptance-artifact-only",
        "Freeze policy drift",
    )
    _require(
        boundary.get("freeze_does_not_deploy_or_tag") is True,
        "Freeze may not deploy or tag",
    )
    security = contract.get("security_boundary")
    _require(
        isinstance(security, dict) and all(value is False for value in security.values()),
        "security boundary drift",
    )
    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(
        transition.get("ready_for_acceptance_candidate") is True,
        "candidate is not ready",
    )
    _require(
        transition.get("next_allowed_stage") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
        "next stage drift",
    )
    _require(
        transition.get("post_freeze_stage") == "NEX-V0.1-RELEASE-CANDIDATE",
        "post-Freeze stage drift",
    )
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "contract checksum drift")


def validate_files_and_markers() -> None:
    expected = {
        ".github/workflows/server-deployment-acceptance.yml": "name: Server deployment acceptance",
        "apps/server/src/nexora/server_deployment_acceptance.py": "class ServerDeploymentAcceptanceError",
        "apps/server/tests/test_server_deployment_acceptance.py": "def test_acceptance_record_round_trip",
        "docs/v0.1/31-server-deployment-acceptance.md": "# NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
        "scripts/run_server_deployment_acceptance.py": "def main() -> int:",
        "tests/test_server_deployment_acceptance.py": "class ServerDeploymentAcceptanceContractTests",
    }
    for relative, marker in expected.items():
        path = ROOT / relative
        _require(path.is_file(), f"missing {relative}")
        _require(marker in path.read_text(encoding="utf-8"), f"missing marker in {relative}")


def main() -> int:
    validate_p2_12_prerequisite()
    contract = load_contract()
    validate_contract(contract)
    validate_files_and_markers()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P2_12_PREREQUISITE=PASS")
    print("NEX_V0_1_SERVER_DEPLOYMENT_ACCEPTANCE_TOOLING=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
