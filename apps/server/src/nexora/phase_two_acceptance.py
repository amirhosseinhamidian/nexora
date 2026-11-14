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
    "repository_contract",
    "backend",
    "migration_cycle",
    "postgresql_accounting",
    "security_inventory",
    "frontend",
    "browser",
}
EXPECTED_MANUAL = {
    "deterministic_accounting_fixture_review",
    "owner_scope_and_immutability_review",
    "import_reconciliation_atomicity_review",
    "projection_rebuild_and_export_review",
    "responsive_bilingual_portfolio_review",
    "no_forbidden_capabilities",
}


class PhaseTwoAcceptanceError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseTwoAcceptanceError(message)


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _object(value: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PhaseTwoAcceptanceError(f"{label} must be valid JSON") from error
    if not isinstance(payload, dict):
        raise PhaseTwoAcceptanceError(f"{label} must be an object")
    return cast(dict[str, Any], payload)


def _field_object(payload: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise PhaseTwoAcceptanceError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise PhaseTwoAcceptanceError(f"{label} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PhaseTwoAcceptanceError(f"{label} must be a timestamp") from error
    _require(parsed.utcoffset() is not None, f"{label} must include UTC")
    return parsed.astimezone(UTC)


def serialize_phase_two_acceptance_record(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("record_checksum", None)
    unsigned["record_checksum"] = hashlib.sha256(_canonical(unsigned)).hexdigest()
    return json.dumps(unsigned, ensure_ascii=False, indent=2, sort_keys=True)


def parse_phase_two_acceptance_record(value: bytes) -> dict[str, Any]:
    payload = _object(value, "Phase 2 acceptance record")
    _require(
        payload.get("schema_version") == "nexora-phase-two-final-acceptance-record-v1",
        "acceptance schema drift",
    )
    candidate = payload.get("candidate_commit_sha")
    _require(isinstance(candidate, str) and SHA.fullmatch(candidate) is not None, "candidate SHA is invalid")
    _require(isinstance(payload.get("branch"), str) and payload["branch"], "acceptance branch is missing")
    _require(payload.get("acceptance_profile") == "local_reference_portfolio", "acceptance profile drift")
    _require(
        isinstance(payload.get("environment_label"), str) and payload["environment_label"],
        "acceptance environment is missing",
    )
    _timestamp(payload.get("generated_at"), "acceptance generated_at")

    prior = _field_object(payload, "prior_freeze", "prior Freeze evidence")
    _require(prior.get("p2_11_ready") is True, "P2-11 prerequisite is not frozen")
    _require(
        prior.get("p2_11_commit_sha") == "df6e05aa4d71a9f8b844e4c1b333449223e7dff3",
        "P2-11 Freeze commit drift",
    )
    _require(
        prior.get("p2_11_record_checksum") == "e8070032a9579a0545847994e9bb0b426310f110ec6c3a0983db2a755d36be1c",
        "P2-11 Freeze record drift",
    )

    capacity = _field_object(payload, "capacity", "capacity evidence")
    _require(capacity.get("candidate_commit_sha") == candidate, "capacity candidate SHA drift")
    _require(capacity.get("environment_label") == payload["environment_label"], "capacity environment drift")
    _require(capacity.get("deployment_network_mode") == "loopback_only", "capacity network mode drift")
    _require(capacity.get("passed") is True, "capacity evidence did not pass")
    _timestamp(capacity.get("generated_at"), "capacity generated_at")
    _require(
        CHECKSUM.fullmatch(str(capacity.get("artifact_checksum"))) is not None,
        "capacity checksum is invalid",
    )

    ci = _field_object(payload, "ci", "CI evidence")
    _require(RUN_URL.fullmatch(str(ci.get("run_url"))) is not None, "CI run URL is invalid")
    _require(ci.get("head_sha") == candidate, "CI head SHA drift")
    _require(ci.get("conclusion") == "success", "CI did not succeed")

    manual = _field_object(payload, "manual", "manual evidence")
    _require(set(manual) == EXPECTED_MANUAL, "manual evidence inventory mismatch")
    _require(all(result == "pass" for result in manual.values()), "manual evidence did not pass")

    gates_value = payload.get("gates")
    if not isinstance(gates_value, list):
        raise PhaseTwoAcceptanceError("acceptance gates must be an array")
    gate_objects = [cast(dict[str, Any], gate) for gate in gates_value if isinstance(gate, dict)]
    _require(len(gate_objects) == len(gates_value), "acceptance gate evidence is invalid")
    _require({gate.get("gate_id") for gate in gate_objects} == EXPECTED_GATES, "gate IDs drift")
    _require(len(gate_objects) == len(EXPECTED_GATES), "acceptance gate inventory mismatch")
    for gate in gate_objects:
        commands_value = gate.get("commands")
        if not isinstance(commands_value, list) or not commands_value:
            raise PhaseTwoAcceptanceError("gate command evidence is missing")
        commands = [cast(dict[str, Any], command) for command in commands_value if isinstance(command, dict)]
        _require(len(commands) == len(commands_value), "gate command evidence is invalid")
        for command in commands:
            _require(
                command.get("passed") is (command.get("exit_code") == 0),
                "gate command outcome is inconsistent",
            )
            argv = command.get("command")
            if not isinstance(argv, list) or not argv:
                raise PhaseTwoAcceptanceError("gate command argv is missing")
            rendered = " ".join(str(argument).casefold() for argument in argv)
            _require(
                not any(marker in rendered for marker in ("://", "password=", "secret=")),
                "gate command evidence contains sensitive material",
            )
        _require(
            gate.get("passed") is all(command.get("passed") is True for command in commands),
            "gate outcome is inconsistent",
        )

    failed = [str(gate["gate_id"]) for gate in gate_objects if gate.get("passed") is not True]
    _require(payload.get("failed_gates") == failed, "failed gate inventory mismatch")
    _require(payload.get("ready_to_freeze_phase_two") is (not failed), "Phase 2 readiness is inconsistent")
    _require(payload.get("phase_two_scope_accepted") is (not failed), "Phase 2 scope outcome is inconsistent")
    _require(payload.get("freeze_commit_policy") == "acceptance-artifact-only", "freeze policy drift")
    _require(payload.get("production_readiness_claimed") is False, "production readiness cannot be claimed")

    server = _field_object(payload, "server_deployment_acceptance", "server acceptance")
    _require(server.get("status") == "deferred_to_server_deployment", "server acceptance must remain deferred")
    _require(server.get("gate_id") == "NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE", "server gate drift")
    _require(server.get("production_readiness_claimed") is False, "server readiness cannot be claimed")

    security = _field_object(payload, "security_boundary", "security boundary")
    _require(bool(security), "security boundary is missing")
    _require(all(enabled is False for enabled in security.values()), "forbidden capability enabled")

    checksum = payload.get("record_checksum")
    unsigned = dict(payload)
    unsigned.pop("record_checksum", None)
    _require(checksum == hashlib.sha256(_canonical(unsigned)).hexdigest(), "acceptance record checksum mismatch")
    return payload
