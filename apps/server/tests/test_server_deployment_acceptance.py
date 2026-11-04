from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from nexora.server_deployment_acceptance import (
    ServerDeploymentAcceptanceError,
    parse_capacity_report,
    parse_operations_drill_report,
    parse_server_deployment_acceptance_record,
    serialize_server_deployment_acceptance_record,
)

SHA = "a" * 40
CHECKSUM = "b" * 64


def signed(payload: dict[str, Any], key: str) -> bytes:
    unsigned = dict(payload)
    unsigned.pop(key, None)
    unsigned[key] = hashlib.sha256(
        json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return (json.dumps(unsigned, ensure_ascii=False) + "\n").encode()


def operations() -> dict[str, Any]:
    return {
        "schema_version": "nexora-private-operations-drill-v1",
        "candidate_commit_sha": SHA,
        "branch": "feature/server-acceptance",
        "environment_label": "de-vps-reference",
        "generated_at": "2026-11-04T10:00:00Z",
        "backup": {
            "backup_id": "backup-20261104",
            "source_commit_sha": SHA,
            "encrypted_sha256": CHECKSUM,
            "runtime_manifest_checksum": CHECKSUM,
            "offsite_manifest_checksum": CHECKSUM,
            "runtime_and_offsite_copies_match": True,
            "duration_seconds": 31.2,
            "passed": True,
        },
        "restore": {
            "duration_seconds": 122.5,
            "database_restored": True,
            "artifacts_restored": True,
            "sessions_revoked": True,
            "service_tokens_revoked": True,
            "service_token_rotation_completed": True,
            "post_restore_health_passed": True,
            "passed": True,
        },
        "retention": {
            "dry_run": True,
            "artifact_plan_checksum": CHECKSUM,
            "backup_plan_checksum": CHECKSUM,
            "immutable_evidence_excluded": True,
            "pinned_artifacts_excluded": True,
            "runtime_copy_counts_as_offsite": False,
            "passed": True,
        },
        "private_deployment": {
            "network_mode": "authenticated_private_overlay",
            "remote_access_enabled": True,
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


def capacity() -> dict[str, Any]:
    return {
        "schema_version": "nexora-private-runtime-benchmark-v1",
        "candidate_commit_sha": SHA,
        "environment_label": "de-vps-reference",
        "generated_at": "2026-11-04T10:00:00Z",
        "deployment_network_mode": "authenticated_private_overlay",
        "public_network_exposure": False,
        "requested_samples": 1000,
        "completed_samples": 1000,
        "throughput_per_second": 120.0,
        "latency_p95_ms": 80.0,
        "status_counts": {"401": 100, "429": 900},
        "retry_after_present_on_all_429": True,
        "immutable_evidence_dropped": False,
        "failure_reasons": [],
        "passed": True,
    }


def acceptance() -> dict[str, Any]:
    manual = {
        "host_identity_and_country": "pass",
        "firewall_and_private_access": "pass",
        "ssh_hardening": "pass",
        "off_host_administration_separation": "pass",
        "clock_synchronization": "pass",
        "secret_file_permissions": "pass",
        "no_forbidden_capabilities": "pass",
    }
    gates = [
        {"gate_id": name, "passed": True}
        for name in (
            "p2_freeze",
            "operations_drill",
            "capacity_overload",
            "private_access",
            "candidate_ci",
            "manual_hardening",
        )
    ]
    evidence = {
        "artifact_checksum": CHECKSUM,
        "candidate_commit_sha": SHA,
        "environment_label": "de-vps-reference",
        "generated_at": "2026-11-04T10:00:00Z",
        "passed": True,
    }
    return {
        "schema_version": "nexora-server-deployment-acceptance-record-v1",
        "candidate_commit_sha": SHA,
        "branch": "feature/server-acceptance",
        "acceptance_profile": "private_vps_de",
        "environment_label": "de-vps-reference",
        "generated_at": "2026-11-04T10:30:00Z",
        "deployment_network_mode": "authenticated_private_overlay",
        "prior_freeze": {
            "p2_12_ready": True,
            "p2_12_commit_sha": "ffe5b1b50c6eb7b09bfe052ad96038de47b779df",
            "p2_12_record_checksum": "114a660b358ba58e16cc3f2b885c20cc72d0b20e0d425f5c266dd2120c0daedb",
        },
        "operations_drill": dict(evidence),
        "capacity": dict(evidence),
        "ci": {
            "run_url": "https://github.com/amirhosseinhamidian/nexora/actions/runs/123456",
            "head_sha": SHA,
            "conclusion": "success",
        },
        "manual": manual,
        "gates": gates,
        "failed_gates": [],
        "ready_to_freeze_server_deployment_acceptance": True,
        "server_deployment_accepted": True,
        "v0_1_private_release_unblocked": True,
        "production_readiness_scope": "private_single_owner_v0.1",
        "public_internet_production_readiness_claimed": False,
        "high_availability_claimed": False,
        "freeze_commit_policy": "acceptance-artifact-only",
        "security_boundary": {
            "public_internet_profile": False,
            "live_execution_capability": False,
            "exchange_credentials": False,
            "wallet_or_fund_transfer": False,
            "autonomous_ai_execution": False,
            "multi_user_identity": False,
        },
    }


def test_operations_and_capacity_reports_are_fail_closed() -> None:
    assert parse_operations_drill_report(signed(operations(), "report_checksum"))["passed"] is True
    assert parse_capacity_report(signed(capacity(), "report_checksum"))["passed"] is True


def test_operations_report_rejects_runtime_copy_as_off_host() -> None:
    payload = operations()
    payload["retention"]["runtime_copy_counts_as_offsite"] = True
    with pytest.raises(ServerDeploymentAcceptanceError, match="runtime backup"):
        parse_operations_drill_report(signed(payload, "report_checksum"))


def test_capacity_report_rejects_public_exposure() -> None:
    payload = capacity()
    payload["public_network_exposure"] = True
    with pytest.raises(ServerDeploymentAcceptanceError, match="public exposure"):
        parse_capacity_report(signed(payload, "report_checksum"))


def test_acceptance_record_round_trip() -> None:
    encoded = serialize_server_deployment_acceptance_record(acceptance()).encode()
    record = parse_server_deployment_acceptance_record(encoded)
    assert record["server_deployment_accepted"] is True
    assert record["v0_1_private_release_unblocked"] is True


def test_acceptance_record_rejects_tampering() -> None:
    record = json.loads(serialize_server_deployment_acceptance_record(acceptance()))
    record["public_internet_production_readiness_claimed"] = True
    with pytest.raises(ServerDeploymentAcceptanceError, match="public readiness"):
        parse_server_deployment_acceptance_record(json.dumps(record).encode())
