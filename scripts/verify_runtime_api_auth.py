#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-runtime-api-auth-contract.json"
FREEZE_PATH = ROOT / "artifacts/p1-07/runtime-api-auth-freeze.json"
EXPECTED_FREEZE_SHA = "57346f95e5fe79160767f49c67b83718ec8a3768"
EXPECTED_FREEZE_CHECKSUM = "05794b71952903ed08ed1cb20cc88e3b7ca46630f06f2a77b3c86706d6983680"
EXPECTED_RUNTIME_CHECKSUM = "4d2abb4eb6b51d847c5a6f16e56c98452719367079095199dca0d1e63e8c6ec5"
CONTRACT_CHECKSUM = "1fae566ea55b14b577860b2785adf851e0c0b2ce3a94b3478ab66b68c1505b3c"
CANDIDATE_SHA = "2a40a03e5a7995e6b845b3ce73e62646449da507"
CANDIDATE_MESSAGE = "fix(nexora): repair P1-07 contract and PostgreSQL CI"
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
APPROVED_EXTENSION_OPERATIONS = {
    "POST /v1/assets",
    "GET /v1/assets",
    "POST /v1/assets/{asset_id}/identifiers",
    "POST /v1/assets/{asset_id}/deactivate",
    "POST /v1/portfolios",
    "GET /v1/portfolios",
    "GET /v1/portfolios/{portfolio_id}",
    "POST /v1/portfolios/{portfolio_id}/archive",
    "POST /v1/accounts",
    "GET /v1/accounts",
    "POST /v1/accounts/{account_id}/close",
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


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _json(path)


def _validate_workflow(
    workflow: object,
    *,
    label: str,
    run_id: int,
    expected_jobs: dict[str, tuple[int, str]],
) -> None:
    _require(isinstance(workflow, dict), f"{label} workflow evidence must be an object")
    _require(workflow.get("run_id") == run_id, f"{label} run ID drift")
    _require(
        workflow.get("run_url") == f"https://github.com/amirhosseinhamidian/nexora/actions/runs/{run_id}",
        f"{label} run URL drift",
    )
    _require(workflow.get("head_sha") == CANDIDATE_SHA, f"{label} workflow head SHA drift")
    _require(workflow.get("event") == "push", f"{label} workflow must be a push run")
    _require(workflow.get("attempt") == 1, f"{label} workflow attempt drift")
    _require(workflow.get("conclusion") == "success", f"{label} workflow did not succeed")
    jobs = workflow.get("jobs")
    _require(isinstance(jobs, dict), f"{label} jobs must be an object")
    _require(set(jobs) == set(expected_jobs), f"{label} job inventory mismatch")
    for job_name, (job_id, displayed_name) in expected_jobs.items():
        job = jobs[job_name]
        _require(isinstance(job, dict), f"{label}/{job_name} must be an object")
        _require(job.get("job_id") == job_id, f"{label}/{job_name} job ID drift")
        _require(job.get("name") == displayed_name, f"{label}/{job_name} name drift")
        _require(job.get("conclusion") == "success", f"{label}/{job_name} did not succeed")


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
    schema_paths = sorted((ROOT / "contracts/runtime/v1/schemas").glob("*.schema.json"))
    schemas: dict[str, dict[str, Any]] = {}
    for path in schema_paths:
        schema = _json(path)
        title = schema.get("title")
        _require(isinstance(title, str) and title, f"runtime schema title missing: {path.name}")
        _require(title not in schemas, f"duplicate runtime schema title: {title}")
        schemas[title] = schema
    _require(len(schemas) == 16, "generated runtime model count drift")
    _require(canonical_checksum(schemas) == EXPECTED_RUNTIME_CHECKSUM, "generated checksum drift")

    manifest_path = ROOT / "apps/server/src/nexora/generated/runtime_contract_manifest.py"
    manifest_spec = importlib.util.spec_from_file_location("runtime_contract_manifest", manifest_path)
    if manifest_spec is None or manifest_spec.loader is None:
        raise RuntimeApiAuthContractError("unable to load generated Python manifest")
    manifest = importlib.util.module_from_spec(manifest_spec)
    manifest_spec.loader.exec_module(manifest)
    _require(manifest.RUNTIME_CONTRACT_CHECKSUM == EXPECTED_RUNTIME_CHECKSUM, "Python manifest checksum drift")
    _require(tuple(schemas) == manifest.RUNTIME_CONTRACT_MODELS, "Python manifest inventory drift")

    typescript = (ROOT / "packages/contracts/src/generated/runtime-api.ts").read_text(encoding="utf-8")
    _require(
        f'export const runtimeContractChecksum = "{EXPECTED_RUNTIME_CHECKSUM}" as const;' in typescript,
        "TypeScript contract checksum drift",
    )

    fixtures = ROOT / "contracts/runtime/v1/fixtures"
    fixture_manifest = _json(fixtures / "manifest.json")
    _require(fixture_manifest.get("schema_version") == "nexora-runtime-fixtures-v1", "fixture schema drift")
    entries = fixture_manifest.get("fixtures")
    _require(isinstance(entries, list) and entries, "runtime fixture inventory missing")
    for entry in entries:
        _require(isinstance(entry, dict), "runtime fixture entry must be an object")
        _require(entry.get("model") in schemas, "runtime fixture references an unknown model")
        fixture_path = fixtures / str(entry.get("path"))
        _require(fixture_path.is_file(), f"runtime fixture missing: {fixture_path.name}")
        _json(fixture_path)


def validate_openapi() -> None:
    document = _json(ROOT / "contracts/runtime/v1/openapi.json")
    operations = {
        f"{method.upper()} {path}"
        for path, path_item in document["paths"].items()
        for method in path_item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    _require(
        operations == EXPECTED_OPERATIONS | APPROVED_EXTENSION_OPERATIONS,
        "OpenAPI operation inventory drift",
    )
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
        "artifacts/p1-07/runtime-api-auth-freeze.json",
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
    for marker in (
        "NEX-P1-07",
        "Frozen",
        "NEX-P1-GAP-001",
        "NEX-P1-GAP-003",
        CANDIDATE_SHA,
        "40372395158",
        "NEX-P1-08",
    ):
        _require(marker in document, f"P1-07 document marker missing: {marker}")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-runtime-api-auth-freeze-v1", "invalid freeze schema")
    _require(record.get("decision_id") == "NEX-P1-07", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "freeze repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "candidate commit message drift")
    _require(
        record.get("candidate_predecessor_sha") == "96dcabc3ea02acac4dc2f9f3bf8f80fa48302e17",
        "candidate predecessor SHA drift",
    )

    primary = record.get("github_actions")
    _validate_workflow(
        primary,
        label="runtime API authentication and contracts",
        run_id=40372395158,
        expected_jobs={
            "cross_language_contract": (121746279114, "cross-language-contract"),
            "runtime_contract": (121746279339, "runtime-contract"),
            "backend": (121746279410, "backend"),
            "postgresql_17": (121746279605, "postgresql-17"),
        },
    )
    _require(primary.get("head_branch") == "feature/v0.1-foundation", "primary workflow branch drift")
    required_markers = {
        "cross_language_contract": ("locked_dependencies_installed", "typescript_contract_typecheck_passed"),
        "runtime_contract": (
            "readiness_freeze_prerequisite_passed",
            "generated_contract_drift_check_passed",
            "runtime_api_verifier_passed",
            "repository_contract_tests_passed",
        ),
        "backend": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "non_integration_tests_passed",
        ),
        "postgresql_17": (
            "private_dsn_fixture_created",
            "upgrade_head_passed",
            "runtime_integration_tests_passed",
            "downgrade_base_passed",
            "rebuild_head_passed",
            "migration_drift_check_passed",
        ),
    }
    for job_name, markers in required_markers.items():
        for marker in markers:
            _require(primary["jobs"][job_name].get(marker) is True, f"{job_name} did not confirm {marker}")

    regression = record.get("regression_workflows")
    _require(isinstance(regression, dict), "regression workflow evidence must be an object")
    expected_regression = {
        "contracts": (
            40372394740,
            {
                "security_boundary": (121746277790, "security-boundary"),
                "scope_contract": (121746278242, "scope-contract"),
                "technical_baseline": (121746278324, "technical-baseline"),
                "integration_contract": (121746278409, "integration-contract"),
                "phase_zero_acceptance": (121746278453, "phase-zero-acceptance"),
            },
        ),
        "application_composition": (
            40372394809,
            {
                "composition_contract": (121746277614, "composition-contract"),
                "backend": (121746278175, "backend"),
            },
        ),
        "postgresql_schema": (
            40372394759,
            {
                "backend": (121746278077, "backend"),
                "postgresql_17": (121746278342, "postgresql-17"),
                "database_contract": (121746278481, "database-contract"),
            },
        ),
        "durable_jobs_outbox": (
            40372394874,
            {
                "durable_contract": (121746278786, "durable-contract"),
                "postgresql_17": (121746279159, "postgresql-17"),
                "backend": (121746279364, "backend"),
            },
        ),
        "runtime_foundation": (
            40372394908,
            {
                "web": (121746278070, "web"),
                "foundation_contract": (121746278552, "foundation-contract"),
                "backend": (121746278594, "backend"),
            },
        ),
        "trd_bot_adapter": (
            40372394808,
            {
                "adapter_contract": (121746290287, "adapter-contract"),
                "backend": (121746290785, "backend"),
            },
        ),
        "phase_one_readiness": (
            40372395066,
            {
                "readiness_contract": (121746279352, "readiness-contract"),
                "web": (121746279764, "web"),
                "backend": (121746279888, "backend"),
            },
        ),
        "single_owner_identity_runtime": (
            40372395325,
            {
                "private_topology": (121746280201, "private-topology"),
                "backend": (121746280505, "backend"),
                "identity_contract": (121746280593, "identity-contract"),
                "postgresql_17": (121746280863, "postgresql-17"),
            },
        ),
    }
    _require(set(regression) == set(expected_regression), "regression workflow inventory mismatch")
    for label, (run_id, jobs) in expected_regression.items():
        _validate_workflow(regression[label], label=label, run_id=run_id, expected_jobs=jobs)

    evidence = record.get("runtime_api_auth_contract")
    _require(isinstance(evidence, dict), "runtime API contract evidence must be an object")
    _require(evidence.get("schema_version") == contract.get("schema_version"), "contract schema mismatch")
    _require(evidence.get("checksum") == CONTRACT_CHECKSUM, "recorded contract checksum drift")
    _require(evidence.get("checksum") == canonical_checksum(contract), "contract checksum mismatch")
    _require(evidence.get("generated_runtime_checksum") == EXPECTED_RUNTIME_CHECKSUM, "generated checksum drift")

    prerequisite = record.get("phase_one_readiness_prerequisite")
    _require(isinstance(prerequisite, dict), "readiness prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-ACCEPTANCE-FREEZE", "readiness decision drift")
    _require(prerequisite.get("frozen") is True, "readiness prerequisite is not frozen")
    readiness = _json(ROOT / "artifacts/p1-acceptance/phase-one-readiness-freeze.json")
    _require(
        prerequisite.get("freeze_record_checksum") == canonical_checksum(readiness) == EXPECTED_FREEZE_CHECKSUM,
        "readiness freeze checksum mismatch",
    )

    _require(record.get("recorded_on") == "2026-10-26", "invalid freeze record date")
    _require(record.get("frozen") is True, "P1-07 is not frozen")
    _require(
        record.get("closed_gaps") == ["NEX-P1-GAP-001", "NEX-P1-GAP-002", "NEX-P1-GAP-003"],
        "frozen gap inventory drift",
    )
    for key in (
        "production_readiness_claimed",
        "public_internet_profile",
        "live_execution_capability",
        "exchange_credentials",
        "wallet_capability",
        "autonomous_ai_execution",
    ):
        _require(record.get(key) is False, f"freeze record cannot enable {key}")
    _require(record.get("next_allowed_stage") == "NEX-P1-08", "post-freeze stage drift")


def main() -> int:
    validate_frozen_phase_one_readiness()
    contract = load_contract()
    validate_contract(contract)
    validate_generated_contracts()
    validate_openapi()
    validate_files_and_documents()
    freeze_record = load_freeze_record()
    validate_freeze_record(freeze_record, contract)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print(f"candidate_commit_sha={freeze_record['candidate_commit_sha']}")
    print("NEX_P1_ACCEPTANCE_FREEZE_PREREQUISITE=PASS")
    print("NEX_P1_07_RUNTIME_API_AUTH=PASS")
    print("NEX_P1_07_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
