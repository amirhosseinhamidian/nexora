from __future__ import annotations

import json
from typing import Any

import pytest
from nexora.phase_three_acceptance import (
    EXPECTED_GATES,
    P3_12_ACCEPTED_SHA,
    PROVIDER_ARTIFACT_DIGEST,
    PROVIDER_ARTIFACT_ID,
    PROVIDER_COMMIT_SHA,
    PROVIDER_PROFILE,
    PROVIDER_SOURCE_CONTRACT,
    PROVIDER_WORKFLOW_RUN_ID,
    PhaseThreeAcceptanceError,
    parse_phase_three_acceptance_record,
    serialize_phase_three_acceptance_record,
)

SHA = "a" * 40


def acceptance() -> dict[str, Any]:
    gates = [
        {
            "gate_id": gate_id,
            "commands": [
                {
                    "label": f"{gate_id} check",
                    "command": ["python", "-m", "pytest", "-q"],
                    "exit_code": 0,
                    "duration_ms": 10,
                    "passed": True,
                }
            ],
            "passed": True,
            "environment_label": "test-host",
        }
        for gate_id in sorted(EXPECTED_GATES)
    ]
    return {
        "schema_version": "nexora-phase-three-final-acceptance-record-v1",
        "candidate_commit_sha": SHA,
        "branch": "feature/phase-three-acceptance",
        "acceptance_profile": "local_reference_decision_intelligence",
        "environment_label": "test-host",
        "generated_at": "2026-11-18T12:00:00.000000Z",
        "prior_stage": {
            "decision_id": "NEX-P3-12",
            "accepted_commit_sha": P3_12_ACCEPTED_SHA,
            "contract_checksum": "b" * 64,
            "same_sha_ci_accepted": True,
        },
        "provider_smoke": {
            "provider_release": "0.3.1",
            "provider_commit_sha": PROVIDER_COMMIT_SHA,
            "workflow_run_id": PROVIDER_WORKFLOW_RUN_ID,
            "artifact_id": PROVIDER_ARTIFACT_ID,
            "artifact_digest": PROVIDER_ARTIFACT_DIGEST,
            "provider_profile": PROVIDER_PROFILE,
            "bound_by_contract": PROVIDER_SOURCE_CONTRACT,
            "real_local_smoke_passed": True,
        },
        "ci": {
            "run_url": "https://github.com/amirhosseinhamidian/nexora/actions/runs/123",
            "head_sha": SHA,
            "conclusion": "success",
        },
        "manual": {
            "projection_replay_and_recovery_review": "pass",
            "owner_scope_and_immutability_review": "pass",
            "export_lineage_and_redaction_review": "pass",
            "responsive_bilingual_accessibility_review": "pass",
            "compatible_provider_smoke_review": "pass",
            "no_forbidden_capabilities": "pass",
        },
        "gates": gates,
        "failed_gates": [],
        "ready_to_freeze_phase_three": True,
        "phase_three_scope_accepted": True,
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


def encoded(payload: dict[str, Any]) -> bytes:
    return serialize_phase_three_acceptance_record(payload).encode()


def test_phase_three_acceptance_record_round_trips() -> None:
    parsed = parse_phase_three_acceptance_record(encoded(acceptance()))
    assert parsed["ready_to_freeze_phase_three"] is True
    assert parsed["phase_three_scope_accepted"] is True


def test_phase_three_acceptance_rejects_ci_drift() -> None:
    payload = acceptance()
    payload["ci"]["head_sha"] = "0" * 40
    with pytest.raises(PhaseThreeAcceptanceError, match="CI head SHA drift"):
        parse_phase_three_acceptance_record(encoded(payload))


def test_phase_three_acceptance_rejects_p3_12_drift() -> None:
    payload = acceptance()
    payload["prior_stage"]["accepted_commit_sha"] = "0" * 40
    with pytest.raises(PhaseThreeAcceptanceError, match="P3-12 accepted SHA drift"):
        parse_phase_three_acceptance_record(encoded(payload))


def test_phase_three_acceptance_rejects_provider_smoke_drift() -> None:
    payload = acceptance()
    payload["provider_smoke"]["artifact_digest"] = "sha256:" + "0" * 64
    with pytest.raises(PhaseThreeAcceptanceError, match="provider smoke digest drift"):
        parse_phase_three_acceptance_record(encoded(payload))


def test_phase_three_acceptance_rejects_failed_manual_evidence() -> None:
    payload = acceptance()
    payload["manual"]["compatible_provider_smoke_review"] = "fail"
    with pytest.raises(PhaseThreeAcceptanceError, match="manual evidence did not pass"):
        parse_phase_three_acceptance_record(encoded(payload))


def test_phase_three_acceptance_rejects_gate_environment_drift() -> None:
    payload = acceptance()
    payload["gates"][0]["environment_label"] = "other-host"
    with pytest.raises(PhaseThreeAcceptanceError, match="gate environment drift"):
        parse_phase_three_acceptance_record(encoded(payload))


def test_phase_three_acceptance_rejects_production_readiness() -> None:
    payload = acceptance()
    payload["production_readiness_claimed"] = True
    with pytest.raises(PhaseThreeAcceptanceError, match="production readiness"):
        parse_phase_three_acceptance_record(encoded(payload))


def test_phase_three_acceptance_rejects_live_execution() -> None:
    payload = acceptance()
    payload["security_boundary"]["live_order_capability"] = True
    with pytest.raises(PhaseThreeAcceptanceError, match="forbidden capability"):
        parse_phase_three_acceptance_record(encoded(payload))


def test_phase_three_acceptance_rejects_sensitive_command_evidence() -> None:
    payload = acceptance()
    payload["gates"][0]["commands"][0]["command"] = ["tool", "postgresql://owner:password@host/database"]
    with pytest.raises(PhaseThreeAcceptanceError, match="sensitive material"):
        parse_phase_three_acceptance_record(encoded(payload))


def test_phase_three_acceptance_rejects_checksum_tamper() -> None:
    payload = json.loads(serialize_phase_three_acceptance_record(acceptance()))
    payload["record_checksum"] = "0" * 64
    with pytest.raises(PhaseThreeAcceptanceError, match="checksum mismatch"):
        parse_phase_three_acceptance_record(json.dumps(payload).encode())


def test_failed_phase_three_acceptance_remains_parseable_but_not_ready() -> None:
    payload = acceptance()
    command = payload["gates"][0]["commands"][0]
    command["exit_code"] = 1
    command["passed"] = False
    payload["gates"][0]["passed"] = False
    payload["failed_gates"] = [payload["gates"][0]["gate_id"]]
    payload["ready_to_freeze_phase_three"] = False
    payload["phase_three_scope_accepted"] = False
    parsed = parse_phase_three_acceptance_record(encoded(payload))
    assert parsed["ready_to_freeze_phase_three"] is False
