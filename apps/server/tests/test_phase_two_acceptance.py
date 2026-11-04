from __future__ import annotations

import json
from typing import Any

import pytest
from nexora.phase_two_acceptance import (
    PhaseTwoAcceptanceError,
    parse_phase_two_acceptance_record,
    serialize_phase_two_acceptance_record,
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
        }
        for gate_id in (
            "repository_contract",
            "backend",
            "migration_cycle",
            "postgresql_accounting",
            "security_inventory",
            "frontend",
            "browser",
        )
    ]
    return {
        "schema_version": "nexora-phase-two-final-acceptance-record-v1",
        "candidate_commit_sha": SHA,
        "branch": "feature/phase-two-acceptance",
        "acceptance_profile": "local_reference_portfolio",
        "environment_label": "test-host",
        "generated_at": "2026-11-04T10:00:00.000000Z",
        "prior_freeze": {
            "p2_11_ready": True,
            "p2_11_commit_sha": "df6e05aa4d71a9f8b844e4c1b333449223e7dff3",
            "p2_11_record_checksum": "e8070032a9579a0545847994e9bb0b426310f110ec6c3a0983db2a755d36be1c",
        },
        "capacity": {
            "artifact_checksum": "b" * 64,
            "candidate_commit_sha": SHA,
            "environment_label": "test-host",
            "deployment_network_mode": "loopback_only",
            "generated_at": "2026-11-04T09:55:00.000000Z",
            "passed": True,
        },
        "ci": {
            "run_url": "https://github.com/amirhosseinhamidian/nexora/actions/runs/123",
            "head_sha": SHA,
            "conclusion": "success",
        },
        "manual": {
            "deterministic_accounting_fixture_review": "pass",
            "owner_scope_and_immutability_review": "pass",
            "import_reconciliation_atomicity_review": "pass",
            "projection_rebuild_and_export_review": "pass",
            "responsive_bilingual_portfolio_review": "pass",
            "no_forbidden_capabilities": "pass",
        },
        "gates": gates,
        "failed_gates": [],
        "ready_to_freeze_phase_two": True,
        "phase_two_scope_accepted": True,
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


def encoded(payload: dict[str, Any]) -> bytes:
    return serialize_phase_two_acceptance_record(payload).encode()


def test_phase_two_acceptance_record_round_trips() -> None:
    parsed = parse_phase_two_acceptance_record(encoded(acceptance()))
    assert parsed["ready_to_freeze_phase_two"] is True
    assert parsed["phase_two_scope_accepted"] is True


def test_phase_two_acceptance_rejects_ci_drift() -> None:
    payload = acceptance()
    payload["ci"]["head_sha"] = "0" * 40
    with pytest.raises(PhaseTwoAcceptanceError, match="CI head SHA drift"):
        parse_phase_two_acceptance_record(encoded(payload))


def test_phase_two_acceptance_rejects_capacity_drift() -> None:
    payload = acceptance()
    payload["capacity"]["environment_label"] = "other-host"
    with pytest.raises(PhaseTwoAcceptanceError, match="capacity environment drift"):
        parse_phase_two_acceptance_record(encoded(payload))


def test_phase_two_acceptance_rejects_failed_manual_evidence() -> None:
    payload = acceptance()
    payload["manual"]["projection_rebuild_and_export_review"] = "fail"
    with pytest.raises(PhaseTwoAcceptanceError, match="manual evidence did not pass"):
        parse_phase_two_acceptance_record(encoded(payload))


def test_phase_two_acceptance_rejects_production_readiness() -> None:
    payload = acceptance()
    payload["production_readiness_claimed"] = True
    with pytest.raises(PhaseTwoAcceptanceError, match="production readiness"):
        parse_phase_two_acceptance_record(encoded(payload))


def test_phase_two_acceptance_rejects_live_execution() -> None:
    payload = acceptance()
    payload["security_boundary"]["live_order_capability"] = True
    with pytest.raises(PhaseTwoAcceptanceError, match="forbidden capability"):
        parse_phase_two_acceptance_record(encoded(payload))


def test_phase_two_acceptance_rejects_sensitive_command_evidence() -> None:
    payload = acceptance()
    payload["gates"][0]["commands"][0]["command"] = ["tool", "postgresql://owner:password@host/database"]
    with pytest.raises(PhaseTwoAcceptanceError, match="sensitive material"):
        parse_phase_two_acceptance_record(encoded(payload))


def test_phase_two_acceptance_rejects_checksum_tamper() -> None:
    payload = json.loads(serialize_phase_two_acceptance_record(acceptance()))
    payload["record_checksum"] = "0" * 64
    with pytest.raises(PhaseTwoAcceptanceError, match="checksum mismatch"):
        parse_phase_two_acceptance_record(json.dumps(payload).encode())


def test_failed_phase_two_acceptance_remains_parseable_but_not_ready() -> None:
    payload = acceptance()
    command = payload["gates"][0]["commands"][0]
    command["exit_code"] = 1
    command["passed"] = False
    payload["gates"][0]["passed"] = False
    payload["failed_gates"] = ["repository_contract"]
    payload["ready_to_freeze_phase_two"] = False
    payload["phase_two_scope_accepted"] = False
    parsed = parse_phase_two_acceptance_record(encoded(payload))
    assert parsed["ready_to_freeze_phase_two"] is False
