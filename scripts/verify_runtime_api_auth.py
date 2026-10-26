#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

from nexora.api import create_app

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-runtime-api-auth-contract.json"
EXPECTED_FREEZE_SHA = "57346f95e5fe79160767f49c67b83718ec8a3768"
EXPECTED_FREEZE_CHECKSUM = "05794b71952903ed08ed1cb20cc88e3b7ca46630f06f2a77b3c86706d6983680"
EXPECTED_RUNTIME_CHECKSUM = "4d2abb4eb6b51d847c5a6f16e56c98452719367079095199dca0d1e63e8c6ec5"
EXPECTED_OPERATIONS = {
    "GET /health/live",
    "GET /version",
    "POST /v1/auth/bootstrap/options",
    "POST /v1/auth/bootstrap/complete",
    "POST /v1/auth/authentication/options",
    "POST /v1/auth/authentication/complete",
    "GET /v1/auth/session",
    "POST /v1/auth/session/rotate",
    "POST /v1/auth/reauthentication/options",
    "POST /v1/auth/reauthentication/complete",
    "POST /v1/auth/registration/options",
    "POST /v1/auth/registration/complete",
    "POST /v1/auth/recovery/options",
    "POST /v1/auth/recovery/complete",
    "POST /v1/auth/logout",
    "POST /v1/auth/logout-all",
}


class RuntimeApiAuthContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeApiAuthContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_phase_one_readiness() -> None:
    path = ROOT / "scripts/verify_phase_one_readiness.py"
    spec = importlib.util.spec_from_file_location("verify_phase_one_readiness", path)
    if spec is None or spec.loader is None:
        raise RuntimeApiAuthContractError("unable to load frozen Phase 1 readiness verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_p1_06()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_files()
    module.validate_documents()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-runtime-api-auth-contract-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P1-07", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-26", "invalid decision date")
    _require(contract.get("status") == "candidate", "P1-07 must remain candidate")

    prerequisite = contract.get("phase_one_readiness_prerequisite")
    _require(isinstance(prerequisite, dict), "Phase 1 readiness prerequisite must be an object")
    _require(prerequisite.get("frozen") is True, "Phase 1 readiness prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == EXPECTED_FREEZE_SHA, "readiness freeze SHA drift")
    freeze = _json(ROOT / prerequisite["freeze_record_path"])
    _require(canonical_checksum(freeze) == EXPECTED_FREEZE_CHECKSUM, "readiness freeze checksum drift")
    _require(prerequisite.get("freeze_record_checksum") == EXPECTED_FREEZE_CHECKSUM, "prerequisite checksum drift")
    _require(prerequisite.get("phase_one_ready") is False, "prior acceptance cannot claim Phase 1 readiness")

    _require(
        contract.get("closed_gaps") == ["NEX-P1-GAP-001", "NEX-P1-GAP-002", "NEX-P1-GAP-003"],
        "P1-07 gap inventory drift",
    )
    runtime = contract.get("runtime_api")
    _require(isinstance(runtime, dict), "runtime API contract must be an object")
    expected_runtime = {
        "schema_version": "nexora-runtime-api-v1",
        "error_schema_version": "nexora-error-envelope-v1",
        "metadata_endpoint": "/version",
        "commit_sha_source": "SOURCE_COMMIT_SHA",
        "correlation_header": "X-Correlation-ID",
        "correlation_id_required_on_every_response": True,
        "canonical_time": "UTC",
        "request_schema_unknown_fields": "reject",
        "mutation_content_type": "application/json",
        "maximum_request_body_bytes": 1_048_576,
        "authenticated_cache_control": "no-store",
    }
    _require(runtime == expected_runtime, "runtime API policy drift")

    lifecycle = contract.get("authentication_lifecycle")
    _require(isinstance(lifecycle, dict), "authentication lifecycle must be an object")
    _require(lifecycle.get("single_owner_only") is True, "identity boundary must remain single-owner")
    _require(lifecycle.get("webauthn_algorithms") == ["ES256", "EdDSA"], "WebAuthn algorithms drift")
    _require(lifecycle.get("user_verification") == "required", "user verification cannot be weakened")
    _require(lifecycle.get("resident_key") == "required", "resident key policy cannot be weakened")
    _require(lifecycle.get("session_cookie") == "__Host-nexora_session", "session cookie drift")
    _require(lifecycle.get("recent_reauthentication_seconds") == 300, "recent reauthentication window drift")
    _require(lifecycle.get("recent_reauthentication_is_durable") is True, "reauthentication must be durable")
    _require(lifecycle.get("recent_reauthentication_migration") == "20261026_0004", "migration drift")

    _require(set(contract.get("operations", [])) == EXPECTED_OPERATIONS, "runtime operation inventory drift")
    toolchain = contract.get("contract_toolchain")
    _require(isinstance(toolchain, dict), "contract toolchain must be an object")
    _require(toolchain.get("source") == "pydantic_runtime_models", "contract source drift")
    _require(toolchain.get("model_count") == 16, "runtime model inventory drift")
    _require(toolchain.get("contract_checksum") == EXPECTED_RUNTIME_CHECKSUM, "runtime checksum drift")
    _require(toolchain.get("unknown_schema_policy") == "fail_closed", "unknown schemas must fail closed")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and security, "security boundary inventory missing")
    for capability, enabled in security.items():
        _require(enabled is False, f"forbidden capability enabled: {capability}")
    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_freeze") is True, "P1-07 is not ready for freeze")
    _require(transition.get("next_allowed_stage") == "NEX-P1-07-FREEZE", "next stage must be freeze")
    _require(transition.get("post_freeze_stage") == "NEX-P1-08", "post-freeze stage drift")


def validate_generated_contracts() -> None:
    generator_path = ROOT / "scripts/generate_runtime_contracts.py"
    spec = importlib.util.spec_from_file_location("generate_runtime_contracts", generator_path)
    if spec is None or spec.loader is None:
        raise RuntimeApiAuthContractError("unable to load runtime contract generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.write_or_check(check=True)
    schemas = module.build_schemas()
    _require(len(schemas) == 16, "generated runtime model count drift")
    _require(module._canonical_checksum(schemas) == EXPECTED_RUNTIME_CHECKSUM, "generated checksum drift")

    manifest_path = ROOT / "apps/server/src/nexora/generated/runtime_contract_manifest.py"
    manifest_spec = importlib.util.spec_from_file_location("runtime_contract_manifest", manifest_path)
    if manifest_spec is None or manifest_spec.loader is None:
        raise RuntimeApiAuthContractError("unable to load generated Python manifest")
    manifest = importlib.util.module_from_spec(manifest_spec)
    manifest_spec.loader.exec_module(manifest)
    _require(manifest.RUNTIME_CONTRACT_CHECKSUM == EXPECTED_RUNTIME_CHECKSUM, "Python manifest checksum drift")
    _require(tuple(schemas) == manifest.RUNTIME_CONTRACT_MODELS, "Python manifest inventory drift")


def validate_openapi() -> None:
    document = create_app().openapi()
    operations = {
        f"{method.upper()} {path}"
        for path, path_item in document["paths"].items()
        for method in path_item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    _require(operations == EXPECTED_OPERATIONS, "OpenAPI operation inventory drift")
    operation_ids: list[str] = []
    for path_item in document["paths"].values():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation_ids.append(operation["operationId"])
            responses = operation["responses"]
            _require("422" in responses, "every public operation must document ErrorEnvelope")
    _require(len(operation_ids) == len(set(operation_ids)), "OpenAPI operation IDs must be unique")
    _require("ErrorEnvelope" in document["components"]["schemas"], "ErrorEnvelope schema missing")


def validate_files_and_documents() -> None:
    required = (
        "alembic/versions/20261026_0004_runtime_authentication_lifecycle.py",
        "apps/server/src/nexora/runtime_contracts.py",
        "apps/server/src/nexora/generated/runtime_contract_manifest.py",
        "apps/server/tests/test_runtime_api.py",
        "contracts/runtime/v1/openapi.json",
        "contracts/runtime/v1/fixtures/manifest.json",
        "packages/contracts/src/generated/runtime-api.ts",
        "scripts/generate_runtime_contracts.py",
        "docs/adr/0021-runtime-api-authentication-and-contract-toolchain.md",
        "docs/v0.1/12-runtime-api-authentication-contract-toolchain.md",
    )
    for relative in required:
        _require((ROOT / relative).is_file(), f"missing P1-07 file: {relative}")

    migration = (ROOT / required[0]).read_text(encoding="utf-8")
    for marker in (
        'revision: str = "20261026_0004"',
        'down_revision: str | None = "20261026_0003"',
        "reauthenticated_at",
    ):
        _require(marker in migration, f"migration marker missing: {marker}")
    document = (ROOT / "docs/v0.1/12-runtime-api-authentication-contract-toolchain.md").read_text(encoding="utf-8")
    for marker in ("NEX-P1-07", "Candidate", "NEX-P1-GAP-001", "NEX-P1-GAP-003", "NEX-P1-07-FREEZE"):
        _require(marker in document, f"P1-07 document marker missing: {marker}")


def main() -> int:
    validate_frozen_phase_one_readiness()
    contract = load_contract()
    validate_contract(contract)
    validate_generated_contracts()
    validate_openapi()
    validate_files_and_documents()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_ACCEPTANCE_FREEZE_PREREQUISITE=PASS")
    print("NEX_P1_07_RUNTIME_API_AUTH=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
