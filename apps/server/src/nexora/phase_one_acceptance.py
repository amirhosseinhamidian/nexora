from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Final, cast

PHASE_ONE_MAX_EVIDENCE_AGE: Final = timedelta(days=7)
SHA = re.compile(r"^[0-9a-f]{40}$")
RUN_URL = re.compile(r"^https://github\.com/amirhosseinhamidian/nexora/actions/runs/[0-9]+$")


class PhaseOneAcceptanceError(ValueError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseOneAcceptanceError(message)


def _object(value: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PhaseOneAcceptanceError(f"{label} must be valid JSON") from error
    if not isinstance(payload, dict):
        raise PhaseOneAcceptanceError(f"{label} must be an object")
    return cast(dict[str, Any], payload)


def _field_object(payload: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise PhaseOneAcceptanceError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise PhaseOneAcceptanceError(f"{label} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PhaseOneAcceptanceError(f"{label} must be a timestamp") from error
    _require(parsed.utcoffset() is not None, f"{label} must include UTC")
    return parsed.astimezone(UTC)


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _validated_checksum(payload: dict[str, Any], label: str) -> None:
    checksum = payload.get("report_checksum")
    _require(isinstance(checksum, str), f"{label} checksum is missing")
    unsigned = dict(payload)
    unsigned.pop("report_checksum", None)
    _require(checksum == sha256_bytes(_canonical(unsigned)), f"{label} checksum mismatch")


def parse_capacity_report(value: bytes) -> dict[str, Any]:
    payload = _object(value, "capacity report")
    _require(payload.get("schema_version") == "nexora-private-runtime-benchmark-v1", "capacity schema drift")
    _require(isinstance(payload.get("candidate_commit_sha"), str), "capacity candidate SHA is missing")
    _require(SHA.fullmatch(payload["candidate_commit_sha"]) is not None, "capacity candidate SHA is invalid")
    _require(
        isinstance(payload.get("environment_label"), str) and payload["environment_label"],
        "capacity environment is missing",
    )
    _timestamp(payload.get("generated_at"), "capacity generated_at")
    _require(payload.get("passed") is True, "capacity report did not pass")
    _require(payload.get("failure_reasons") == [], "capacity report contains failures")
    _require(payload.get("completed_samples") == payload.get("requested_samples"), "capacity samples are incomplete")
    _require(payload.get("minimum_throughput_per_second") == 10, "capacity throughput budget drift")
    _require(float(payload.get("throughput_per_second", 0)) >= 10, "capacity throughput budget missed")
    _require(payload.get("latency_p95_budget_ms") == 300, "capacity latency budget drift")
    _require(float(payload.get("latency_p95_ms", 301)) <= 300, "capacity latency budget exceeded")
    statuses = _field_object(payload, "status_counts", "capacity status counts")
    _require(int(statuses.get("429", 0)) > 0, "capacity report has no overload evidence")
    _require(payload.get("retry_after_present_on_all_429") is True, "capacity Retry-After evidence is incomplete")
    _require(payload.get("immutable_evidence_dropped") is False, "capacity report claims evidence loss")
    _validated_checksum(payload, "capacity report")
    return payload


def parse_operations_drill_report(value: bytes) -> dict[str, Any]:
    payload = _object(value, "operations drill report")
    _require(payload.get("schema_version") == "nexora-private-operations-drill-v1", "operations drill schema drift")
    _require(isinstance(payload.get("candidate_commit_sha"), str), "operations candidate SHA is missing")
    _require(SHA.fullmatch(payload["candidate_commit_sha"]) is not None, "operations candidate SHA is invalid")
    _require(
        isinstance(payload.get("environment_label"), str) and payload["environment_label"],
        "operations environment is missing",
    )
    _timestamp(payload.get("generated_at"), "operations generated_at")
    _require(payload.get("passed") is True, "operations drill did not pass")
    _require(payload.get("failure_reasons") == [], "operations drill contains failures")
    backup = _field_object(payload, "backup", "backup evidence")
    restore = _field_object(payload, "restore", "restore evidence")
    retention = _field_object(payload, "retention", "retention evidence")
    deployment = _field_object(payload, "private_deployment", "deployment evidence")
    for item, label in ((backup, "backup"), (restore, "restore"), (retention, "retention"), (deployment, "deployment")):
        _require(item.get("passed") is True, f"{label} evidence did not pass")
    _require(backup.get("runtime_and_offsite_copies_match") is True, "backup copies do not match")
    _require(backup.get("source_commit_sha") == payload["candidate_commit_sha"], "backup candidate SHA drift")
    for key in (
        "database_restored",
        "artifacts_restored",
        "sessions_revoked",
        "service_tokens_revoked",
        "service_token_rotation_completed",
        "post_restore_health_passed",
    ):
        _require(restore.get(key) is True, f"restore evidence missing {key}")
    _require(retention.get("dry_run") is True, "retention evidence must be a dry-run")
    _require(retention.get("immutable_evidence_excluded") is True, "retention may include immutable evidence")
    _require(retention.get("pinned_artifacts_excluded") is True, "retention may include pinned artifacts")
    _require(retention.get("runtime_copy_counts_as_offsite") is False, "runtime backup cannot count as offsite")
    _require(float(backup.get("duration_seconds", 0)) > 0, "backup duration is invalid")
    restore_duration = float(restore.get("duration_seconds", 0))
    _require(0 < restore_duration <= 4 * 60 * 60, "restore RTO was not met")
    for key in ("https_443_only", "health_ready", "web_shell", "worker_restart_reclaim"):
        _require(deployment.get(key) is True, f"deployment evidence missing {key}")
    _validated_checksum(payload, "operations drill report")
    return payload


def serialize_phase_one_acceptance_record(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("record_checksum", None)
    unsigned["record_checksum"] = sha256_bytes(_canonical(unsigned))
    return json.dumps(unsigned, ensure_ascii=False, indent=2, sort_keys=True)


def parse_phase_one_acceptance_record(value: bytes) -> dict[str, Any]:
    payload = _object(value, "Phase 1 acceptance record")
    _require(payload.get("schema_version") == "nexora-phase-one-final-acceptance-record-v1", "acceptance schema drift")
    candidate = payload.get("candidate_commit_sha")
    _require(isinstance(candidate, str) and SHA.fullmatch(candidate) is not None, "acceptance candidate SHA is invalid")
    _require(isinstance(payload.get("branch"), str) and payload["branch"], "acceptance branch is missing")
    _require(
        isinstance(payload.get("environment_label"), str) and payload["environment_label"],
        "acceptance environment is missing",
    )
    _timestamp(payload.get("generated_at"), "acceptance generated_at")
    prior = _field_object(payload, "prior_freeze", "prior freeze evidence")
    _require(prior.get("p1_12_ready") is True, "P1-12 prerequisite is not frozen")
    _require(prior.get("p1_12_commit_sha") == "1af9161925a71c4154801bb6ac4f533f4a8e21b8", "P1-12 commit drift")
    _require(
        prior.get("p1_12_record_checksum") == "49d9c3c2427d4154445a25c61be8945dca4b46cbcfe43ce25e538c37a457cda6",
        "P1-12 record drift",
    )
    for key in ("capacity", "operations_drill"):
        evidence = _field_object(payload, key, f"{key} evidence")
        _require(evidence.get("candidate_commit_sha") == candidate, f"{key} candidate SHA drift")
        _require(evidence.get("environment_label") == payload["environment_label"], f"{key} environment drift")
        _require(evidence.get("passed") is True, f"{key} evidence did not pass")
        _require(
            re.fullmatch(r"[0-9a-f]{64}", str(evidence.get("artifact_checksum"))) is not None,
            f"{key} checksum is invalid",
        )
    ci = _field_object(payload, "ci", "CI evidence")
    _require(RUN_URL.fullmatch(str(ci.get("run_url"))) is not None, "CI run URL is invalid")
    _require(ci.get("head_sha") == candidate, "CI head SHA drift")
    _require(ci.get("conclusion") == "success", "CI did not succeed")
    manual = _field_object(payload, "manual", "manual evidence")
    expected_manual = {
        "fresh_clone_install",
        "passkey_session_and_csrf_lifecycle",
        "trd_bot_sync_and_idempotency",
        "private_backup_restore_and_retention",
        "responsive_bilingual_web_shell",
        "no_forbidden_capabilities",
    }
    _require(set(manual) == expected_manual, "manual evidence inventory mismatch")
    _require(all(value == "pass" for value in manual.values()), "manual evidence did not pass")
    gates_value = payload.get("gates")
    if not isinstance(gates_value, list):
        raise PhaseOneAcceptanceError("acceptance gates must be an array")
    gates = cast(list[object], gates_value)
    _require(len(gates) == 6, "acceptance gate inventory mismatch")
    expected_gates = {
        "repository_contract",
        "backend",
        "migration_cycle",
        "postgresql_resilience",
        "frontend",
        "browser",
    }
    gate_objects = [cast(dict[str, Any], gate) for gate in gates if isinstance(gate, dict)]
    _require({gate.get("gate_id") for gate in gate_objects} == expected_gates, "gate IDs drift")
    _require(len(gate_objects) == len(gates), "acceptance gate evidence is invalid")
    for gate in gate_objects:
        commands_value = gate.get("commands")
        if not isinstance(commands_value, list) or not commands_value:
            raise PhaseOneAcceptanceError("gate command evidence is missing")
        command_items = cast(list[object], commands_value)
        commands = [cast(dict[str, Any], command) for command in command_items if isinstance(command, dict)]
        _require(len(commands) == len(command_items), "gate command evidence is invalid")
        for command in commands:
            _require(
                command.get("passed") is (command.get("exit_code") == 0),
                "gate command outcome is inconsistent",
            )
            argv_value = command.get("command")
            if not isinstance(argv_value, list) or not argv_value:
                raise PhaseOneAcceptanceError("gate command argv is missing")
            argv = cast(list[object], argv_value)
            rendered = " ".join(str(argument).casefold() for argument in argv)
            _require(
                not any(marker in rendered for marker in ("://", "password=", "secret=")),
                "gate command evidence contains sensitive material",
            )
        _require(
            gate.get("passed") is all(command.get("passed") is True for command in commands),
            "gate outcome is inconsistent",
        )
    computed_failed = [str(gate["gate_id"]) for gate in gate_objects if gate.get("passed") is not True]
    _require(payload.get("failed_gates") == computed_failed, "failed gate inventory mismatch")
    _require(
        payload.get("ready_to_freeze_phase_one") is (not computed_failed),
        "Phase 1 readiness is inconsistent",
    )
    _require(payload.get("freeze_commit_policy") == "acceptance-artifact-only", "freeze commit policy drift")
    security = _field_object(payload, "security_boundary", "security boundary")
    _require(bool(security), "security boundary is missing")
    _require(all(value is False for value in security.values()), "forbidden capability enabled")
    checksum = payload.get("record_checksum")
    unsigned = dict(payload)
    unsigned.pop("record_checksum", None)
    _require(checksum == sha256_bytes(_canonical(unsigned)), "acceptance record checksum mismatch")
    return payload
