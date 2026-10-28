from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from nexora.phase_one_acceptance import (
    PhaseOneAcceptanceError,
    parse_capacity_report,
    parse_operations_drill_report,
    parse_phase_one_acceptance_record,
    serialize_phase_one_acceptance_record,
)

SHA = "a" * 40
NOW = "2026-10-28T10:00:00.000000Z"


def _checksum(payload: dict[str, Any]) -> dict[str, Any]:
    signed = dict(payload)
    encoded = json.dumps(signed, sort_keys=True, separators=(",", ":")).encode()
    signed["report_checksum"] = hashlib.sha256(encoded).hexdigest()
    return signed


def _bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True).encode()


def capacity() -> dict[str, Any]:
    return _checksum(
        {
            "schema_version": "nexora-private-runtime-benchmark-v1",
            "candidate_commit_sha": SHA,
            "environment_label": "test-host",
            "generated_at": NOW,
            "deployment_network_mode": "loopback_only",
            "public_network_exposure": False,
            "requested_samples": 100,
            "completed_samples": 100,
            "status_counts": {"401": 75, "429": 25},
            "throughput_per_second": 25.0,
            "minimum_throughput_per_second": 10,
            "latency_p95_ms": 120.0,
            "latency_p95_budget_ms": 300,
            "retry_after_present_on_all_429": True,
            "immutable_evidence_dropped": False,
            "failure_reasons": [],
            "passed": True,
        }
    )


def drill() -> dict[str, Any]:
    return _checksum(
        {
            "schema_version": "nexora-private-operations-drill-v1",
            "candidate_commit_sha": SHA,
            "environment_label": "test-host",
            "generated_at": NOW,
            "backup": {
                "source_commit_sha": SHA,
                "runtime_and_offsite_copies_match": True,
                "duration_seconds": 5.0,
                "passed": True,
            },
            "restore": {
                "database_restored": True,
                "artifacts_restored": True,
                "sessions_revoked": True,
                "service_tokens_revoked": True,
                "service_token_rotation_completed": True,
                "post_restore_health_passed": True,
                "duration_seconds": 20.0,
                "passed": True,
            },
            "retention": {
                "dry_run": True,
                "immutable_evidence_excluded": True,
                "pinned_artifacts_excluded": True,
                "runtime_copy_counts_as_offsite": False,
                "passed": True,
            },
            "private_deployment": {
                "network_mode": "loopback_only",
                "remote_access_enabled": False,
                "public_network_exposure": False,
                "https_443_only": True,
                "health_ready": True,
                "web_shell": True,
                "worker_restart_reclaim": True,
                "passed": True,
            },
            "failure_reasons": [],
            "passed": True,
        }
    )


def acceptance() -> dict[str, Any]:
    gate_ids = (
        "repository_contract",
        "backend",
        "migration_cycle",
        "postgresql_resilience",
        "frontend",
        "browser",
    )
    return {
        "schema_version": "nexora-phase-one-final-acceptance-record-v1",
        "candidate_commit_sha": SHA,
        "branch": "feature/v0.1-foundation",
        "environment_label": "test-host",
        "generated_at": NOW,
        "deployment_network_mode": "loopback_only",
        "trd_bot_provider_mode": "disabled_incompatible_provider",
        "prior_freeze": {
            "p1_12_ready": True,
            "p1_12_commit_sha": "1af9161925a71c4154801bb6ac4f533f4a8e21b8",
            "p1_12_record_checksum": "49d9c3c2427d4154445a25c61be8945dca4b46cbcfe43ce25e538c37a457cda6",
        },
        "capacity": {
            "candidate_commit_sha": SHA,
            "environment_label": "test-host",
            "passed": True,
            "deployment_network_mode": "loopback_only",
            "artifact_checksum": "b" * 64,
        },
        "operations_drill": {
            "candidate_commit_sha": SHA,
            "environment_label": "test-host",
            "passed": True,
            "deployment_network_mode": "loopback_only",
            "artifact_checksum": "c" * 64,
        },
        "ci": {
            "run_url": "https://github.com/amirhosseinhamidian/nexora/actions/runs/123",
            "head_sha": SHA,
            "conclusion": "success",
        },
        "manual": {
            "fresh_clone_install": "pass",
            "passkey_session_and_csrf_lifecycle": "pass",
            "trd_bot_contract_and_idempotency": "pass",
            "private_backup_restore_and_retention": "pass",
            "responsive_bilingual_web_shell": "pass",
            "no_forbidden_capabilities": "pass",
        },
        "gates": [
            {
                "gate_id": gate_id,
                "passed": True,
                "commands": [
                    {
                        "label": "fixture",
                        "command": ["python", "-m", "pytest"],
                        "exit_code": 0,
                        "duration_ms": 1,
                        "passed": True,
                    }
                ],
            }
            for gate_id in gate_ids
        ],
        "failed_gates": [],
        "ready_to_freeze_phase_one": True,
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


def test_capacity_report_is_checksum_bound_and_fail_closed() -> None:
    assert parse_capacity_report(_bytes(capacity()))["passed"] is True
    changed = capacity()
    changed["status_counts"] = {"401": 100}
    with pytest.raises(PhaseOneAcceptanceError, match="overload evidence"):
        parse_capacity_report(_bytes(changed))


def test_capacity_report_rejects_public_network_mode() -> None:
    changed = capacity()
    changed["deployment_network_mode"] = "public_internet"
    changed = _checksum({key: value for key, value in changed.items() if key != "report_checksum"})
    with pytest.raises(PhaseOneAcceptanceError, match="network mode"):
        parse_capacity_report(_bytes(changed))


def test_operations_drill_requires_restore_and_protected_retention() -> None:
    assert parse_operations_drill_report(_bytes(drill()))["passed"] is True
    changed = drill()
    changed["restore"]["sessions_revoked"] = False
    with pytest.raises(PhaseOneAcceptanceError, match="sessions_revoked"):
        parse_operations_drill_report(_bytes(changed))


def test_operations_drill_rejects_loopback_remote_access() -> None:
    changed = drill()
    changed["private_deployment"]["remote_access_enabled"] = True
    changed = _checksum({key: value for key, value in changed.items() if key != "report_checksum"})
    with pytest.raises(PhaseOneAcceptanceError, match="remote-access"):
        parse_operations_drill_report(_bytes(changed))


def test_final_acceptance_record_round_trips() -> None:
    encoded = (serialize_phase_one_acceptance_record(acceptance()) + "\n").encode()
    parsed = parse_phase_one_acceptance_record(encoded)
    assert parsed["ready_to_freeze_phase_one"] is True


def test_final_acceptance_rejects_ci_drift() -> None:
    payload = acceptance()
    payload["ci"]["head_sha"] = "0" * 40
    encoded = serialize_phase_one_acceptance_record(payload).encode()
    with pytest.raises(PhaseOneAcceptanceError, match="CI head SHA drift"):
        parse_phase_one_acceptance_record(encoded)


def test_final_acceptance_rejects_network_mode_drift() -> None:
    payload = acceptance()
    payload["capacity"]["deployment_network_mode"] = "authenticated_private_overlay"
    encoded = serialize_phase_one_acceptance_record(payload).encode()
    with pytest.raises(PhaseOneAcceptanceError, match="network mode drift"):
        parse_phase_one_acceptance_record(encoded)


def test_final_acceptance_rejects_enabled_incompatible_provider() -> None:
    payload = acceptance()
    payload["trd_bot_provider_mode"] = "enabled_compatible_provider"
    encoded = serialize_phase_one_acceptance_record(payload).encode()
    with pytest.raises(PhaseOneAcceptanceError, match="provider mode drift"):
        parse_phase_one_acceptance_record(encoded)


def test_final_acceptance_rejects_live_execution() -> None:
    payload = acceptance()
    payload["security_boundary"]["live_execution_capability"] = True
    encoded = serialize_phase_one_acceptance_record(payload).encode()
    with pytest.raises(PhaseOneAcceptanceError, match="forbidden capability"):
        parse_phase_one_acceptance_record(encoded)


def test_final_acceptance_rejects_sensitive_command_evidence() -> None:
    payload = acceptance()
    payload["gates"][0]["commands"][0]["command"] = ["tool", "postgresql://owner:password@host/database"]
    encoded = serialize_phase_one_acceptance_record(payload).encode()
    with pytest.raises(PhaseOneAcceptanceError, match="sensitive material"):
        parse_phase_one_acceptance_record(encoded)


def test_final_acceptance_rejects_checksum_tamper() -> None:
    payload = json.loads(serialize_phase_one_acceptance_record(acceptance()))
    payload["record_checksum"] = "0" * 64
    with pytest.raises(PhaseOneAcceptanceError, match="checksum mismatch"):
        parse_phase_one_acceptance_record(_bytes(payload))


def test_failed_acceptance_record_remains_parseable_but_not_ready() -> None:
    payload = acceptance()
    payload["gates"][0]["commands"][0]["exit_code"] = 1
    payload["gates"][0]["commands"][0]["passed"] = False
    payload["gates"][0]["passed"] = False
    payload["failed_gates"] = ["repository_contract"]
    payload["ready_to_freeze_phase_one"] = False
    encoded = serialize_phase_one_acceptance_record(payload).encode()
    parsed = parse_phase_one_acceptance_record(encoded)
    assert parsed["ready_to_freeze_phase_one"] is False
