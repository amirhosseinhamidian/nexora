#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-three-roadmap.json"
P2_ACCEPTANCE_PATH = ROOT / "artifacts/p2-12/phase-two-final-acceptance.json"
SERVER_CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-server-deployment-acceptance.json"

CONTRACT_CHECKSUM = "a4906ed219d57e67e147fe55198329ac534fb3be9b6191955a4d9e632edc6951"
P2_ACCEPTANCE_CANONICAL_CHECKSUM = "1fcf0bacdf223c3b5186e0bc2a1f8e763dc66a2c3e532d76f8073386456049e9"
P2_ACCEPTANCE_RECORD_CHECKSUM = "114a660b358ba58e16cc3f2b885c20cc72d0b20e0d425f5c266dd2120c0daedb"
P2_CANDIDATE_SHA = "f71ef1840c09b12259ef519bd27ffd508b1913f2"
P2_FREEZE_SHA = "ffe5b1b50c6eb7b09bfe052ad96038de47b779df"
SERVER_CONTRACT_CHECKSUM = "7f80d36b857fe1921d25c0fd78f2b394c0a61d93868b761390e6930f710288ad"

EXPECTED_STAGES = [f"NEX-P3-{number:02d}" for number in range(14)]
EXPECTED_REVIEW_ACTIONS = {"accept", "reject", "defer"}
EXPECTED_RELEASE_BLOCKERS = {"v0.1-production-deployment", "v0.1-release"}
FORBIDDEN_CAPABILITIES = {
    "saas",
    "multi_user",
    "public_internet_deployment",
    "exchange_credentials",
    "wallet_private_keys_or_signing",
    "fund_transfer",
    "live_order_capability",
    "autonomous_ai_execution",
    "ml_training_or_inference",
    "financial_advice",
    "tax_advice",
    "direct_trd_bot_database_access",
}


class PhaseThreeRoadmapError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseThreeRoadmapError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_phase_two_prerequisite(path: Path = P2_ACCEPTANCE_PATH) -> None:
    acceptance = _json(path)
    _require(
        canonical_checksum(acceptance) == P2_ACCEPTANCE_CANONICAL_CHECKSUM,
        "P2-12 acceptance artifact drift",
    )
    _require(
        acceptance.get("record_checksum") == P2_ACCEPTANCE_RECORD_CHECKSUM,
        "P2-12 record checksum drift",
    )
    _require(acceptance.get("candidate_commit_sha") == P2_CANDIDATE_SHA, "P2-12 candidate drift")
    _require(acceptance.get("phase_two_scope_accepted") is True, "Phase 2 scope was not accepted")
    _require(acceptance.get("ready_to_freeze_phase_two") is True, "Phase 2 was not ready to freeze")
    _require(acceptance.get("failed_gates") == [], "P2-12 contains failed gates")
    _require(
        acceptance.get("production_readiness_claimed") is False,
        "P2-12 cannot claim production readiness",
    )
    server_gate = acceptance.get("server_deployment_acceptance")
    _require(isinstance(server_gate, dict), "P2-12 server gate must be an object")
    _require(
        server_gate.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
        "P2-12 server gate drift",
    )
    _require(
        server_gate.get("status") == "deferred_to_server_deployment",
        "P2-12 server gate was not deferred",
    )
    _require(set(server_gate.get("blocks", [])) == EXPECTED_RELEASE_BLOCKERS, "P2-12 blockers drift")


def validate_server_gate(path: Path = SERVER_CONTRACT_PATH) -> None:
    server = _json(path)
    _require(canonical_checksum(server) == SERVER_CONTRACT_CHECKSUM, "server acceptance contract drift")
    _require(
        server.get("decision_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
        "server gate ID drift",
    )
    deployment = server.get("deployment")
    _require(isinstance(deployment, dict), "server deployment boundary must be an object")
    _require(deployment.get("host_type") == "private_vps", "server host type drift")
    _require(deployment.get("country_code") == "DE", "server country drift")
    _require(deployment.get("public_network_exposure") is False, "public server exposure enabled")
    _require(deployment.get("network_mode") == "authenticated_private_overlay", "network mode drift")
    evidence = set(server.get("required_evidence", []))
    _require("independent_off_host_backup_copy" in evidence, "off-host backup evidence removed")
    _require("restore_drill_within_rto" in evidence, "restore evidence removed")
    _require("server_capacity_and_overload_benchmark" in evidence, "capacity evidence removed")
    security = server.get("security_boundary")
    _require(isinstance(security, dict), "server security boundary must be an object")
    _require(not any(security.values()), "server gate enabled a forbidden capability")


def _validate_roadmap(contract: dict[str, Any]) -> None:
    roadmap = contract.get("phase_three_roadmap")
    _require(isinstance(roadmap, list), "Phase 3 roadmap must be a list")
    stage_ids = [stage.get("stage_id") for stage in roadmap if isinstance(stage, dict)]
    _require(stage_ids == EXPECTED_STAGES, "Phase 3 stage order drift")
    _require(roadmap[0].get("status") == "candidate", "P3-00 must remain the only candidate")
    _require(
        all(stage.get("status") == "planned" for stage in roadmap[1:]),
        "later Phase 3 stages must remain planned",
    )


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-phase-three-roadmap-v1", "invalid schema version")
    _require(contract.get("decision_id") == "NEX-P3-00", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-11-04", "invalid decision date")
    _require(contract.get("status") == "candidate", "P3-00 must remain a candidate")

    prerequisite = contract.get("phase_two_prerequisite")
    _require(isinstance(prerequisite, dict), "Phase 2 prerequisite must be an object")
    _require(prerequisite.get("frozen") is True, "Phase 2 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_FREEZE_SHA, "Phase 2 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_CANDIDATE_SHA,
        "Phase 2 candidate drift",
    )
    _require(
        prerequisite.get("acceptance_record_canonical_checksum") == P2_ACCEPTANCE_CANONICAL_CHECKSUM,
        "Phase 2 acceptance checksum drift",
    )
    _require(
        prerequisite.get("acceptance_record_checksum") == P2_ACCEPTANCE_RECORD_CHECKSUM,
        "Phase 2 record checksum drift",
    )
    _require(prerequisite.get("phase_two_scope_accepted") is True, "Phase 2 must be accepted")
    _require(
        prerequisite.get("production_readiness_claimed") is False,
        "Phase 2 prerequisite cannot claim production readiness",
    )

    amendment = contract.get("roadmap_amendment")
    _require(isinstance(amendment, dict), "roadmap amendment must be an object")
    _require(amendment.get("local_development_may_continue") is True, "local continuation not authorized")
    _require(amendment.get("local_acceptance_is_production_acceptance") is False, "local production claim")
    _require(amendment.get("server_acceptance_is_removed") is False, "server gate removed")
    _require(amendment.get("server_acceptance_is_bypassed") is False, "server gate bypassed")
    _require(amendment.get("production_deployment_blocked") is True, "production deployment unblocked")
    _require(amendment.get("v0_1_release_blocked") is True, "v0.1 release unblocked")

    server = contract.get("server_deployment_gate")
    _require(isinstance(server, dict), "server deployment gate must be an object")
    _require(server.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE", "server gate ID drift")
    _require(server.get("debt_id") == "NEX-DEBT-P1-13-001", "server debt drift")
    _require(server.get("status") == "deferred_until_private_vps_available", "server gate status drift")
    _require(set(server.get("required_before", [])) == EXPECTED_RELEASE_BLOCKERS, "release blockers drift")
    _require(server.get("required_evidence_unchanged") is True, "server evidence was weakened")
    _require(server.get("production_readiness_claimed") is False, "server production claim")

    boundary = contract.get("phase_three_boundary")
    _require(isinstance(boundary, dict), "Phase 3 boundary must be an object")
    _require(set(boundary.get("human_review_actions", [])) == EXPECTED_REVIEW_ACTIONS, "review actions drift")
    for key in ("decision_evidence_is_immutable", "human_review_is_separate_from_engine_recommendation"):
        _require(boundary.get(key) is True, f"Phase 3 invariant disabled: {key}")
    for key in ("live_execution", "financial_advice_claimed", "autonomous_ai_execution", "ml_training_or_inference"):
        _require(boundary.get(key) is False, f"Phase 3 cannot enable {key}")

    dependency = contract.get("trd_bot_dependency")
    _require(isinstance(dependency, dict), "TRD Bot dependency must be an object")
    _require(dependency.get("current_release") == "0.3.0", "current TRD Bot release drift")
    _require(dependency.get("current_release_compatible") is False, "TRD Bot 0.3.0 cannot be compatible")
    _require(dependency.get("target_release") == "0.3.1", "TRD Bot target release drift")
    _require(dependency.get("p3_03_freeze_requires_compatible_provider") is True, "provider gate removed")
    _require(dependency.get("provider_integration_smoke_required") is True, "provider smoke removed")
    _require(dependency.get("direct_database_access") is False, "direct TRD Bot database access enabled")

    _validate_roadmap(contract)

    acceptance = contract.get("phase_three_acceptance")
    _require(isinstance(acceptance, dict), "Phase 3 acceptance must be an object")
    required = {key: value for key, value in acceptance.items() if key != "production_readiness_claimed"}
    _require(all(value is True for value in required.values()), "Phase 3 acceptance requirement disabled")
    _require(acceptance.get("production_readiness_claimed") is False, "Phase 3 production claim")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security boundary must be an object")
    _require(set(security) == FORBIDDEN_CAPABILITIES, "security capability inventory drift")
    _require(not any(security.values()), "Phase 3 enabled a forbidden capability")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("next_allowed_stage") == "NEX-P3-00-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P3-01", "post-Freeze stage drift")
    _require(transition.get("freeze_before_implementation") is True, "implementation opened before Freeze")
    _require(transition.get("requires_successful_ci_on_candidate_sha") is True, "candidate CI gate removed")


def validate_files_and_markers() -> None:
    expected = {
        "README.md": "`NEX-P3-00` is the current candidate",
        "docs/v0.1/30-phase-two-final-acceptance.md": "`NEX-P3-00`; continuing bounded local development",
        "docs/v0.1/31-server-deployment-acceptance.md": "# NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE",
        "docs/v0.1/32-phase-three-roadmap-and-deferred-deployment.md": "# NEX-P3-00",
        ".github/workflows/phase-three-roadmap.yml": "name: Phase 3 roadmap",
        "tests/test_phase_three_roadmap.py": "class PhaseThreeRoadmapContractTests",
    }
    for relative, marker in expected.items():
        content = (ROOT / relative).read_text(encoding="utf-8")
        _require(marker in content, f"{relative} is missing the P3-00 marker")


def main() -> int:
    validate_phase_two_prerequisite()
    validate_server_gate()
    contract = load_contract()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P3-00 contract checksum drift")
    validate_files_and_markers()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P2_12_PREREQUISITE=PASS")
    print("NEX_V0_1_SERVER_DEPLOYMENT_GATE=PRESERVED_DEFERRED")
    print("NEX_P3_00_PHASE_THREE_ROADMAP=PASS")
    print("NEX_P3_00_READY_FOR_CANDIDATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
