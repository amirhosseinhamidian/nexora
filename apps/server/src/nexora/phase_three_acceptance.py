from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any, cast

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
RUN_URL = re.compile(r"^https://github\.com/amirhosseinhamidian/nexora/actions/runs/[0-9]+$")
P3_12_ACCEPTED_SHA = "7fb3a707dc6b3c059eb2e65b06490385f18c3b1b"
PROVIDER_COMMIT_SHA = "3097276ed77cd212101797654452456b7fbc61de"
PROVIDER_WORKFLOW_RUN_ID = 43210235551
PROVIDER_ARTIFACT_ID = 13939958030
PROVIDER_ARTIFACT_DIGEST = "sha256:d1ec79aa429891ae94a36a4d65d573c3b97550ceaffa343b3df8989286d3375d"
PROVIDER_PROFILE = "contracts/integration/v1/trd-bot-v0.3.1-provider-profile.json"
PROVIDER_SOURCE_CONTRACT = "contracts/nexora-v0.1-durable-decision-event-projection.json"
EXPECTED_GATES = {
    "repository_contract",
    "backend",
    "migration_cycle",
    "postgresql_projection_recovery",
    "phase_three_contract_chain",
    "security_inventory",
    "export_coverage",
    "frontend",
    "browser",
    "provider_smoke_evidence",
}
EXPECTED_MANUAL = {
    "projection_replay_and_recovery_review",
    "owner_scope_and_immutability_review",
    "export_lineage_and_redaction_review",
    "responsive_bilingual_accessibility_review",
    "compatible_provider_smoke_review",
    "no_forbidden_capabilities",
}


class PhaseThreeAcceptanceError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseThreeAcceptanceError(message)


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _object(value: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PhaseThreeAcceptanceError(f"{label} must be valid JSON") from error
    if not isinstance(payload, dict):
        raise PhaseThreeAcceptanceError(f"{label} must be an object")
    return cast(dict[str, Any], payload)


def _field_object(payload: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise PhaseThreeAcceptanceError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise PhaseThreeAcceptanceError(f"{label} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PhaseThreeAcceptanceError(f"{label} must be a timestamp") from error
    _require(parsed.utcoffset() is not None, f"{label} must include UTC")
    return parsed.astimezone(UTC)


def serialize_phase_three_acceptance_record(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("record_checksum", None)
    unsigned["record_checksum"] = hashlib.sha256(_canonical(unsigned)).hexdigest()
    return json.dumps(unsigned, ensure_ascii=False, indent=2, sort_keys=True)


def parse_phase_three_acceptance_record(value: bytes) -> dict[str, Any]:
    payload = _object(value, "Phase 3 acceptance record")
    _require(
        payload.get("schema_version") == "nexora-phase-three-final-acceptance-record-v1",
        "acceptance schema drift",
    )
    candidate = payload.get("candidate_commit_sha")
    _require(isinstance(candidate, str) and SHA.fullmatch(candidate) is not None, "candidate SHA is invalid")
    _require(isinstance(payload.get("branch"), str) and payload["branch"], "acceptance branch is missing")
    _require(
        payload.get("acceptance_profile") == "local_reference_decision_intelligence",
        "acceptance profile drift",
    )
    _require(
        isinstance(payload.get("environment_label"), str) and payload["environment_label"],
        "acceptance environment is missing",
    )
    _timestamp(payload.get("generated_at"), "acceptance generated_at")

    prior = _field_object(payload, "prior_stage", "P3-12 evidence")
    _require(prior.get("decision_id") == "NEX-P3-12", "P3-12 decision drift")
    _require(prior.get("accepted_commit_sha") == P3_12_ACCEPTED_SHA, "P3-12 accepted SHA drift")
    _require(prior.get("same_sha_ci_accepted") is True, "P3-12 CI acceptance is missing")
    contract_checksum = prior.get("contract_checksum")
    _require(
        isinstance(contract_checksum, str) and re.fullmatch(r"[0-9a-f]{64}", contract_checksum) is not None,
        "P3-12 contract checksum is invalid",
    )

    provider = _field_object(payload, "provider_smoke", "provider smoke evidence")
    _require(provider.get("provider_release") == "0.3.1", "provider release drift")
    _require(provider.get("provider_commit_sha") == PROVIDER_COMMIT_SHA, "provider commit drift")
    _require(provider.get("workflow_run_id") == PROVIDER_WORKFLOW_RUN_ID, "provider workflow drift")
    _require(provider.get("artifact_id") == PROVIDER_ARTIFACT_ID, "provider smoke artifact drift")
    _require(provider.get("artifact_digest") == PROVIDER_ARTIFACT_DIGEST, "provider smoke digest drift")
    _require(DIGEST.fullmatch(str(provider.get("artifact_digest"))) is not None, "provider digest is invalid")
    _require(provider.get("provider_profile") == PROVIDER_PROFILE, "provider profile drift")
    _require(provider.get("bound_by_contract") == PROVIDER_SOURCE_CONTRACT, "provider source contract drift")
    _require(provider.get("real_local_smoke_passed") is True, "provider smoke did not pass")

    ci = _field_object(payload, "ci", "CI evidence")
    _require(RUN_URL.fullmatch(str(ci.get("run_url"))) is not None, "CI run URL is invalid")
    _require(ci.get("head_sha") == candidate, "CI head SHA drift")
    _require(ci.get("conclusion") == "success", "CI did not succeed")

    manual = _field_object(payload, "manual", "manual evidence")
    _require(set(manual) == EXPECTED_MANUAL, "manual evidence inventory mismatch")
    _require(all(result == "pass" for result in manual.values()), "manual evidence did not pass")

    gates_value = payload.get("gates")
    if not isinstance(gates_value, list):
        raise PhaseThreeAcceptanceError("acceptance gates must be an array")
    gate_objects = [cast(dict[str, Any], gate) for gate in gates_value if isinstance(gate, dict)]
    _require(len(gate_objects) == len(gates_value), "acceptance gate evidence is invalid")
    _require({gate.get("gate_id") for gate in gate_objects} == EXPECTED_GATES, "gate IDs drift")
    _require(len(gate_objects) == len(EXPECTED_GATES), "acceptance gate inventory mismatch")
    for gate in gate_objects:
        _require(gate.get("environment_label") == payload["environment_label"], "gate environment drift")
        commands_value = gate.get("commands")
        if not isinstance(commands_value, list) or not commands_value:
            raise PhaseThreeAcceptanceError("gate command evidence is missing")
        commands = [cast(dict[str, Any], command) for command in commands_value if isinstance(command, dict)]
        _require(len(commands) == len(commands_value), "gate command evidence is invalid")
        for command in commands:
            _require(
                command.get("passed") is (command.get("exit_code") == 0),
                "gate command outcome is inconsistent",
            )
            argv = command.get("command")
            if not isinstance(argv, list) or not argv:
                raise PhaseThreeAcceptanceError("gate command argv is missing")
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
    _require(payload.get("ready_to_freeze_phase_three") is (not failed), "Phase 3 readiness is inconsistent")
    _require(payload.get("phase_three_scope_accepted") is (not failed), "Phase 3 scope outcome is inconsistent")
    _require(payload.get("freeze_commit_policy") == "acceptance-artifact-only", "freeze policy drift")
    _require(payload.get("production_readiness_claimed") is False, "production readiness cannot be claimed")

    server = _field_object(payload, "server_deployment_acceptance", "server acceptance")
    _require(
        server.get("status") == "deferred_until_private_vps_available",
        "server acceptance must remain deferred",
    )
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
