from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any, cast

SHA = re.compile(r"^[0-9a-f]{40}$")
CHECKSUM = re.compile(r"^[0-9a-f]{64}$")
RUN_URL = re.compile(r"^https://github\.com/amirhosseinhamidian/nexora/actions/runs/[0-9]+$")
EXPECTED_GATES = {
    "p2_freeze",
    "operations_drill",
    "capacity_overload",
    "private_access",
    "candidate_ci",
    "manual_hardening",
}
EXPECTED_MANUAL = {
    "host_identity_and_country",
    "firewall_and_private_access",
    "ssh_hardening",
    "off_host_administration_separation",
    "clock_synchronization",
    "secret_file_permissions",
    "no_forbidden_capabilities",
}


class ServerDeploymentAcceptanceError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ServerDeploymentAcceptanceError(message)


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _object(value: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ServerDeploymentAcceptanceError(f"{label} must be valid JSON") from error
    if not isinstance(payload, dict):
        raise ServerDeploymentAcceptanceError(f"{label} must be an object")
    return cast(dict[str, Any], payload)


def _field_object(payload: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ServerDeploymentAcceptanceError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ServerDeploymentAcceptanceError(f"{label} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ServerDeploymentAcceptanceError(f"{label} must be a timestamp") from error
    _require(parsed.utcoffset() is not None, f"{label} must include UTC")
    return parsed.astimezone(UTC)


def parse_operations_drill_report(value: bytes) -> dict[str, Any]:
    payload = _object(value, "operations drill report")
    _require(
        payload.get("schema_version") == "nexora-private-operations-drill-v1",
        "drill schema drift",
    )
    candidate = payload.get("candidate_commit_sha")
    _require(
        isinstance(candidate, str) and SHA.fullmatch(candidate) is not None,
        "drill candidate SHA is invalid",
    )
    _require(
        isinstance(payload.get("branch"), str) and payload["branch"],
        "drill branch is missing",
    )
    _require(
        isinstance(payload.get("environment_label"), str) and payload["environment_label"],
        "drill environment is missing",
    )
    _timestamp(payload.get("generated_at"), "drill generated_at")

    backup = _field_object(payload, "backup", "backup evidence")
    _require(backup.get("source_commit_sha") == candidate, "backup candidate SHA drift")
    _require(
        backup.get("runtime_and_offsite_copies_match") is True,
        "off-host backup copy mismatch",
    )
    _require(backup.get("passed") is True, "backup evidence did not pass")
    for key in (
        "encrypted_sha256",
        "runtime_manifest_checksum",
        "offsite_manifest_checksum",
    ):
        _require(
            CHECKSUM.fullmatch(str(backup.get(key))) is not None,
            f"backup {key} is invalid",
        )
    _require(float(backup.get("duration_seconds", 0)) > 0, "backup duration is invalid")

    restore = _field_object(payload, "restore", "restore evidence")
    _require(
        0 < float(restore.get("duration_seconds", 0)) <= 4 * 60 * 60,
        "restore exceeded RTO",
    )
    for key in (
        "database_restored",
        "artifacts_restored",
        "sessions_revoked",
        "service_tokens_revoked",
        "service_token_rotation_completed",
        "post_restore_health_passed",
        "passed",
    ):
        _require(restore.get(key) is True, f"restore evidence requires {key}")

    retention = _field_object(payload, "retention", "retention evidence")
    for key in (
        "dry_run",
        "immutable_evidence_excluded",
        "pinned_artifacts_excluded",
        "passed",
    ):
        _require(retention.get(key) is True, f"retention evidence requires {key}")
    _require(
        retention.get("runtime_copy_counts_as_offsite") is False,
        "runtime backup cannot count as off-host",
    )
    for key in ("artifact_plan_checksum", "backup_plan_checksum"):
        _require(
            CHECKSUM.fullmatch(str(retention.get(key))) is not None,
            f"retention {key} is invalid",
        )

    private = _field_object(payload, "private_deployment", "private deployment evidence")
    _require(
        private.get("network_mode") == "authenticated_private_overlay",
        "server requires private overlay",
    )
    _require(
        private.get("remote_access_enabled") is True,
        "private remote access was not verified",
    )
    _require(private.get("public_network_exposure") is False, "public exposure is forbidden")
    for key in (
        "https_443_only",
        "health_ready",
        "web_shell",
        "worker_restart_reclaim",
        "passed",
    ):
        _require(private.get(key) is True, f"private deployment requires {key}")
    _require(payload.get("failure_reasons") == [], "drill contains failure reasons")
    _require(payload.get("passed") is True, "operations drill did not pass")
    checksum = payload.get("report_checksum")
    _require(
        isinstance(checksum, str) and CHECKSUM.fullmatch(checksum) is not None,
        "drill checksum is invalid",
    )
    unsigned = dict(payload)
    unsigned.pop("report_checksum", None)
    _require(sha256_bytes(_canonical(unsigned)) == checksum, "drill checksum mismatch")
    return payload


def parse_capacity_report(value: bytes) -> dict[str, Any]:
    payload = _object(value, "capacity report")
    _require(
        payload.get("schema_version") == "nexora-private-runtime-benchmark-v1",
        "capacity schema drift",
    )
    candidate = payload.get("candidate_commit_sha")
    _require(
        isinstance(candidate, str) and SHA.fullmatch(candidate) is not None,
        "capacity candidate SHA is invalid",
    )
    _require(
        isinstance(payload.get("environment_label"), str) and payload["environment_label"],
        "capacity environment is missing",
    )
    _timestamp(payload.get("generated_at"), "capacity generated_at")
    _require(
        payload.get("deployment_network_mode") == "authenticated_private_overlay",
        "capacity network mode drift",
    )
    _require(
        payload.get("public_network_exposure") is False,
        "capacity report permits public exposure",
    )
    requested = payload.get("requested_samples")
    completed = payload.get("completed_samples")
    _require(
        isinstance(requested, int) and requested >= 1000,
        "capacity requires at least 1000 samples",
    )
    _require(completed == requested, "capacity samples are incomplete")
    _require(
        float(payload.get("throughput_per_second", 0)) >= 10,
        "capacity throughput is below budget",
    )
    _require(
        float(payload.get("latency_p95_ms", 10**9)) <= 300,
        "capacity p95 exceeds budget",
    )
    counts = _field_object(payload, "status_counts", "capacity status counts")
    _require(int(counts.get("429", 0)) > 0, "capacity report must exercise overload")
    _require(payload.get("retry_after_present_on_all_429") is True, "Retry-After is missing")
    _require(
        payload.get("immutable_evidence_dropped") is False,
        "immutable evidence was dropped",
    )
    _require(payload.get("failure_reasons") == [], "capacity report contains failures")
    _require(payload.get("passed") is True, "capacity report did not pass")
    checksum = payload.get("report_checksum")
    _require(
        isinstance(checksum, str) and CHECKSUM.fullmatch(checksum) is not None,
        "capacity checksum is invalid",
    )
    unsigned = dict(payload)
    unsigned.pop("report_checksum", None)
    _require(sha256_bytes(_canonical(unsigned)) == checksum, "capacity checksum mismatch")
    return payload


def serialize_server_deployment_acceptance_record(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("record_checksum", None)
    unsigned["record_checksum"] = sha256_bytes(_canonical(unsigned))
    return json.dumps(unsigned, ensure_ascii=False, indent=2, sort_keys=True)


def parse_server_deployment_acceptance_record(value: bytes) -> dict[str, Any]:
    payload = _object(value, "server deployment acceptance record")
    _require(
        payload.get("schema_version") == "nexora-server-deployment-acceptance-record-v1",
        "acceptance schema drift",
    )
    candidate = payload.get("candidate_commit_sha")
    _require(
        isinstance(candidate, str) and SHA.fullmatch(candidate) is not None,
        "candidate SHA is invalid",
    )
    _require(
        isinstance(payload.get("branch"), str) and payload["branch"],
        "acceptance branch is missing",
    )
    _require(
        payload.get("acceptance_profile") == "private_vps_de",
        "acceptance profile drift",
    )
    _require(
        isinstance(payload.get("environment_label"), str) and payload["environment_label"],
        "environment is missing",
    )
    _timestamp(payload.get("generated_at"), "acceptance generated_at")
    _require(
        payload.get("deployment_network_mode") == "authenticated_private_overlay",
        "network mode drift",
    )

    prior = _field_object(payload, "prior_freeze", "prior Freeze evidence")
    _require(prior.get("p2_12_ready") is True, "P2-12 prerequisite is not frozen")
    _require(
        prior.get("p2_12_commit_sha") == "ffe5b1b50c6eb7b09bfe052ad96038de47b779df",
        "P2-12 commit drift",
    )
    _require(
        prior.get("p2_12_record_checksum") == "114a660b358ba58e16cc3f2b885c20cc72d0b20e0d425f5c266dd2120c0daedb",
        "P2-12 record drift",
    )

    for key in ("operations_drill", "capacity"):
        evidence = _field_object(payload, key, f"{key} evidence")
        _require(
            evidence.get("candidate_commit_sha") == candidate,
            f"{key} candidate SHA drift",
        )
        _require(
            evidence.get("environment_label") == payload["environment_label"],
            f"{key} environment drift",
        )
        _timestamp(evidence.get("generated_at"), f"{key} generated_at")
        _require(
            CHECKSUM.fullmatch(str(evidence.get("artifact_checksum"))) is not None,
            f"{key} checksum is invalid",
        )
        _require(evidence.get("passed") is True, f"{key} did not pass")

    ci = _field_object(payload, "ci", "CI evidence")
    _require(ci.get("head_sha") == candidate, "CI candidate SHA drift")
    _require(ci.get("conclusion") == "success", "CI did not succeed")
    _require(
        isinstance(ci.get("run_url"), str) and RUN_URL.fullmatch(ci["run_url"]) is not None,
        "CI URL is invalid",
    )

    manual = _field_object(payload, "manual", "manual evidence")
    _require(set(manual) == EXPECTED_MANUAL, "manual evidence inventory drift")
    _require(
        all(manual[key] == "pass" for key in EXPECTED_MANUAL),
        "manual evidence did not pass",
    )
    gates = payload.get("gates")
    if not isinstance(gates, list):
        raise ServerDeploymentAcceptanceError("gates must be a list")
    gate_ids = {item.get("gate_id") for item in gates if isinstance(item, dict)}
    _require(
        gate_ids == EXPECTED_GATES and len(gates) == len(EXPECTED_GATES),
        "gate inventory drift",
    )
    _require(
        all(isinstance(item, dict) and item.get("passed") is True for item in gates),
        "gate failure",
    )
    _require(payload.get("failed_gates") == [], "failed gates must be empty")
    _require(
        payload.get("ready_to_freeze_server_deployment_acceptance") is True,
        "acceptance is not ready",
    )
    _require(
        payload.get("server_deployment_accepted") is True,
        "server deployment was not accepted",
    )
    _require(
        payload.get("v0_1_private_release_unblocked") is True,
        "private release is still blocked",
    )
    _require(
        payload.get("production_readiness_scope") == "private_single_owner_v0.1",
        "readiness scope drift",
    )
    _require(
        payload.get("public_internet_production_readiness_claimed") is False,
        "public readiness is forbidden",
    )
    _require(
        payload.get("freeze_commit_policy") == "acceptance-artifact-only",
        "Freeze policy drift",
    )

    security = _field_object(payload, "security_boundary", "security boundary")
    _require(
        all(value is False for value in security.values()),
        "security boundary enabled a forbidden capability",
    )
    checksum = payload.get("record_checksum")
    _require(
        isinstance(checksum, str) and CHECKSUM.fullmatch(checksum) is not None,
        "record checksum is invalid",
    )
    unsigned = dict(payload)
    unsigned.pop("record_checksum", None)
    _require(sha256_bytes(_canonical(unsigned)) == checksum, "record checksum mismatch")
    return payload
