#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-portfolio-api-export.json"
FREEZE_PATH = ROOT / "artifacts/p2-09/portfolio-api-export-freeze.json"
P2_08_VERIFIER_PATH = ROOT / "scripts/verify_paper_shadow_projection.py"
P2_08_FREEZE_PATH = ROOT / "artifacts/p2-08/trd-bot-paper-shadow-projection-freeze.json"
P2_08_FREEZE_COMMIT = "37866ad1f3635bcbdeb7569366140e21b23485bc"
P2_08_CANDIDATE_COMMIT = "d53f0e90acaac2de3157e9c535f99070bfb73a9d"
P2_08_FREEZE_CHECKSUM = "90d374d2bb5b81e491ebfd645f7cc320e1828c9bd5de88c0748b819e50f58d34"
CONTRACT_CHECKSUM = "108303ee0b61d7b2778a26cb719e7a27c3ceeed59618db03b132765a66932766"
CANDIDATE_SHA = "13704691a091497d7cc26a09e3403b18246b0ec7"
CANDIDATE_TREE_SHA = "d1a301eb0118ed1fda7568643d276627a0faf5b2"
CANDIDATE_MESSAGE = "fix(nexora): align export OpenAPI verification"
CANDIDATE_PREDECESSOR = "37866ad1f3635bcbdeb7569366140e21b23485bc"
CANDIDATE_LINEAGE_CHECKSUM = "481713c929aef7b5981b19ddfc4ebe34af85b079b737606dd42bff009e06f655"
EXPECTED_WORKFLOW_RUNS = 24
EXPECTED_CHECKS = 78
WORKFLOW_RUNS_CHECKSUM = "ff018d50c77249409a4bb8585283e6c3c061e4cd1a86bf3f95bd8030c84f98aa"
CHECKS_CHECKSUM = "412793dc91a540341dca87f394da676800791f3fcd85807a24ed763cbcadc95c"

EXPECTED_ENTITIES = {
    "paper_shadow_projection_read_api",
    "portfolio_export_request",
    "portfolio_export_manifest",
    "portfolio_export_bundle",
}
EXPECTED_OPERATIONS = {
    "GET /v1/trd-bot/paper-shadow-projection",
    "POST /v1/portfolio-exports",
    "GET /v1/exports/{artifact_type}/{artifact_id}/versions/{version}/download",
}
EXPECTED_AI_SAFE_EXCLUSIONS = {
    "credentials",
    "tokens",
    "recovery_codes",
    "private_keys",
    "session_identifiers",
    "raw_security_audit_context",
    "provider_raw_payloads",
    "external_account_references",
    "free_text_financial_context",
}


class PortfolioApiExportContractError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PortfolioApiExportContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.relative_to(ROOT)} must contain an object")
    return payload


def canonical_checksum(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p2_08() -> None:
    spec = importlib.util.spec_from_file_location("verify_paper_shadow_projection", P2_08_VERIFIER_PATH)
    _require(spec is not None and spec.loader is not None, "unable to load P2-08 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contract = module.load_contract()
    freeze = module.load_freeze_record()
    module.validate_frozen_p2_07()
    module.validate_contract(contract)
    module.validate_runtime_markers()
    module.validate_freeze_record(freeze, contract)
    module.validate_workflow()
    _require(canonical_checksum(freeze) == P2_08_FREEZE_CHECKSUM, "P2-08 Freeze checksum drift")
    _require(freeze.get("candidate_commit_sha") == P2_08_CANDIDATE_COMMIT, "P2-08 candidate drift")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-portfolio-api-export-contract-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P2-09", "invalid decision")
    _require(contract.get("status") == "candidate", "P2-09 must remain a candidate before Freeze")

    prerequisite = contract.get("prerequisite")
    _require(isinstance(prerequisite, dict), "prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-08", "P2-08 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P2-08 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_08_FREEZE_COMMIT, "P2-08 Freeze SHA drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_08_CANDIDATE_COMMIT,
        "P2-08 candidate SHA drift",
    )
    _require(
        prerequisite.get("freeze_record_path") == P2_08_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-08 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_08_FREEZE_CHECKSUM, "Freeze checksum drift")

    scope = contract.get("scope")
    _require(isinstance(scope, dict), "scope must be an object")
    _require(set(scope.get("entities", [])) == EXPECTED_ENTITIES, "entity inventory drift")
    _require(set(scope.get("profiles", [])) == {"private_complete", "ai_safe"}, "profile inventory drift")
    _require(set(scope.get("content_formats", [])) == {"json", "csv", "parquet"}, "format inventory drift")
    _require(scope.get("delivery_format") == "manifest_backed_zip", "delivery format drift")
    for excluded in ("dashboard_included", "public_download_included", "live_trading_included"):
        _require(scope.get(excluded) is False, f"P2-09 cannot enable {excluded}")

    api = contract.get("api_boundary")
    _require(isinstance(api, dict), "API boundary must be an object")
    _require(set(api.get("operations", [])) == EXPECTED_OPERATIONS, "API operation inventory drift")
    for required in (
        "session_authentication_required",
        "mutation_origin_and_csrf_required",
        "owner_scope_derived_from_session",
        "strict_request_schema",
        "authenticated_download_path_only",
    ):
        _require(api.get(required) is True, f"API boundary requires {required}")
    _require(api.get("owner_id_accepted_from_request") is False, "owner override enabled")
    _require(api.get("public_url_returned") is False, "public export URL enabled")

    invariants = contract.get("export_invariants")
    _require(isinstance(invariants, dict), "export invariants must be an object")
    for required in (
        "complete_export_required",
        "partial_export_forbidden",
        "deterministic_dataset_ordering",
        "deterministic_record_ordering",
        "deterministic_zip_metadata",
        "canonical_json_required",
        "analysis_ready_csv_required",
        "real_parquet_required",
        "snapshot_checksum_required",
        "file_checksums_required",
        "bundle_checksum_required",
        "lineage_required",
        "uncertainty_required",
        "timestamp_required",
        "financial_decimal_strings_required",
        "binary_float_forbidden",
    ):
        _require(invariants.get(required) is True, f"export invariant requires {required}")
    _require(invariants.get("maximum_records") == 100000, "record budget drift")
    _require(invariants.get("maximum_uncompressed_bytes") == 134217728, "byte budget drift")
    _require(
        invariants.get("capacity_behavior") == "fail_closed_without_partial_artifact",
        "partial capacity behavior enabled",
    )

    profile = contract.get("profile_boundary")
    _require(isinstance(profile, dict), "profile boundary must be an object")
    for required in (
        "private_complete_contains_all_allowed_portfolio_fields",
        "ai_safe_uses_explicit_exclusion_policy",
        "security_and_identity_tables_excluded_from_all_profiles",
        "excluded_fields_declared_in_manifest",
    ):
        _require(profile.get(required) is True, f"profile boundary requires {required}")
    _require(
        set(profile.get("ai_safe_excluded_categories", [])) == EXPECTED_AI_SAFE_EXCLUSIONS,
        "AI-safe exclusion inventory drift",
    )

    persistence = contract.get("persistence")
    _require(isinstance(persistence, dict), "persistence must be an object")
    for required in (
        "source_snapshot_is_repeatable_read",
        "immutable_artifact_publication",
        "existing_financial_tables_only",
    ):
        _require(persistence.get(required) is True, f"persistence requires {required}")
    _require(persistence.get("artifact_namespace") == "export", "artifact namespace drift")
    _require(persistence.get("artifact_type") == "portfolio-export", "artifact type drift")
    _require(set(persistence.get("retention_classes", [])) == {"pinned_export", "unpinned_export"}, "retention drift")
    _require(persistence.get("new_tables") == [], "P2-09 cannot add mutable tables")
    _require(persistence.get("new_migration_required") is False, "unexpected migration requirement")
    _require(persistence.get("public_bucket") is False, "public artifact bucket enabled")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security boundary must be an object")
    _require(all(value is False for value in security.values()), "forbidden capability enabled")
    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_candidate") is True, "candidate is not ready")
    _require(transition.get("next_allowed_stage") == "NEX-P2-09-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P2-10", "post-Freeze stage drift")
    _require(transition.get("freeze_before_dashboard") is True, "dashboard Freeze boundary missing")


def validate_runtime_markers() -> None:
    domain = (ROOT / "apps/server/src/nexora/portfolio_export.py").read_text(encoding="utf-8")
    source = (ROOT / "apps/server/src/nexora/adapters/postgresql/portfolio_export.py").read_text(encoding="utf-8")
    contracts = (ROOT / "apps/server/src/nexora/portfolio_export_contracts.py").read_text(encoding="utf-8")
    api = (ROOT / "apps/server/src/nexora/api.py").read_text(encoding="utf-8")
    composition = (ROOT / "apps/server/src/nexora/composition.py").read_text(encoding="utf-8")
    dependency = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for marker in (
        "class PortfolioExportService",
        "class PortfolioExportProfile",
        "def build_portfolio_export(",
        "MAX_EXPORT_RECORDS: Final = 100_000",
        "MAX_UNCOMPRESSED_BYTES: Final = 128 * 1024 * 1024",
        'public_download": False',
    ):
        _require(marker in domain, f"export domain marker missing: {marker}")
    for marker in (
        "class PostgreSQLPortfolioExportSource",
        'execution_options={"isolation_level": "REPEATABLE READ"}',
        "AI_SAFE_EXCLUDED_FIELDS",
        'if name == "owner_id"',
    ):
        _require(marker in source, f"export source marker missing: {marker}")
    for forbidden in ("BootstrapToken", "RecoveryCode", "BrowserSession", "WebAuthnCredential", "SecurityAuditEvent"):
        _require(forbidden not in source, f"security or identity model entered export source: {forbidden}")
    for marker in ("CreatePortfolioExportRequest", 'extra="forbid"', "public_download: Literal[False]"):
        _require(marker in contracts, f"export API contract marker missing: {marker}")
    for marker in ('"/v1/portfolio-exports"', '"/v1/trd-bot/paper-shadow-projection"'):
        _require(marker in api, f"portfolio API route missing: {marker}")
    _require("portfolio_export_service" in composition, "portfolio export service is not composed")
    _require('"pyarrow==22.0.0"' in dependency, "locked Parquet runtime dependency is missing")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-portfolio-api-export-freeze-v1", "invalid Freeze schema")
    _require(record.get("decision_id") == "NEX-P2-09", "invalid Freeze decision")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "Freeze repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_tree_sha") == CANDIDATE_TREE_SHA, "candidate tree drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "candidate message drift")
    _require(record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR, "candidate predecessor drift")

    lineage = record.get("candidate_lineage")
    _require(isinstance(lineage, list), "candidate lineage must be an array")
    _require(len(lineage) == 3, "candidate lineage must contain implementation and both corrective commits")
    _require(canonical_checksum(lineage) == CANDIDATE_LINEAGE_CHECKSUM, "candidate lineage drift")
    _require(lineage[0].get("parent_sha") == CANDIDATE_PREDECESSOR, "candidate lineage base drift")
    _require(lineage[-1].get("sha") == CANDIDATE_SHA, "candidate lineage does not end at accepted SHA")
    for previous, current in itertools.pairwise(lineage):
        _require(current.get("parent_sha") == previous.get("sha"), "candidate lineage continuity drift")

    workflows = record.get("workflow_runs")
    _require(isinstance(workflows, list), "workflow runs must be an array")
    _require(len(workflows) == EXPECTED_WORKFLOW_RUNS, "workflow run inventory drift")
    _require(canonical_checksum(workflows) == WORKFLOW_RUNS_CHECKSUM, "workflow run evidence drift")
    run_ids = {workflow.get("run_id") for workflow in workflows}
    _require(len(run_ids) == EXPECTED_WORKFLOW_RUNS, "workflow run IDs must be unique")
    _require(all(workflow.get("conclusion") == "success" for workflow in workflows), "workflow did not succeed")

    checks = record.get("checks")
    _require(isinstance(checks, list), "checks must be an array")
    _require(len(checks) == EXPECTED_CHECKS, "check inventory drift")
    _require(canonical_checksum(checks) == CHECKS_CHECKSUM, "check evidence drift")
    job_ids = {check.get("job_id") for check in checks}
    _require(len(job_ids) == EXPECTED_CHECKS, "check job IDs must be unique")
    _require(all(check.get("run_id") in run_ids for check in checks), "check references an unknown workflow")
    _require(all(check.get("conclusion") == "success" for check in checks), "check did not succeed")
    _require(
        record.get("check_summary") == {"total": 78, "successful": 78, "failed": 0, "pending": 0},
        "check summary drift",
    )

    contract_evidence = record.get("portfolio_api_export_contract")
    _require(isinstance(contract_evidence, dict), "portfolio API/export contract evidence must be an object")
    _require(contract_evidence.get("schema_version") == contract.get("schema_version"), "contract schema drift")
    _require(contract_evidence.get("path") == CONTRACT_PATH.relative_to(ROOT).as_posix(), "contract path drift")
    _require(contract_evidence.get("checksum") == canonical_checksum(contract), "contract evidence drift")
    _require(contract_evidence.get("checksum") == CONTRACT_CHECKSUM, "contract checksum drift")

    prerequisite = record.get("p2_08_prerequisite")
    _require(isinstance(prerequisite, dict), "P2-08 prerequisite evidence must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-08", "P2-08 decision drift")
    _require(prerequisite.get("frozen") is True, "P2-08 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_08_FREEZE_COMMIT, "P2-08 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_08_CANDIDATE_COMMIT,
        "P2-08 candidate drift",
    )
    _require(
        prerequisite.get("freeze_record_path") == P2_08_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-08 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_08_FREEZE_CHECKSUM, "P2-08 checksum drift")

    _require(record.get("recorded_on") == "2026-11-03", "Freeze record date drift")
    _require(record.get("frozen") is True, "P2-09 must be frozen")
    for completed in (
        "paper_shadow_read_api_complete",
        "private_complete_export_complete",
        "ai_safe_export_complete",
        "deterministic_json_csv_parquet_zip_complete",
        "repeatable_read_snapshot_complete",
        "immutable_private_artifact_publication_complete",
        "authenticated_owner_scoped_download_complete",
        "lineage_uncertainty_and_checksums_complete",
        "openapi_contract_complete",
    ):
        _require(record.get(completed) is True, f"Freeze completion missing: {completed}")
    for deferred in ("dashboard_complete", "external_provider_smoke_claimed", "production_readiness_claimed"):
        _require(record.get(deferred) is False, f"Freeze cannot claim {deferred}")
    for forbidden in (
        "public_internet_deployment",
        "multi_user",
        "exchange_credentials",
        "wallet_private_keys_or_signing",
        "fund_transfer",
        "live_order_capability",
        "autonomous_ai_execution",
        "ml_training_or_inference",
        "financial_advice",
        "tax_advice",
        "direct_trd_bot_database_access",
        "journal_mutation",
        "nav_or_pnl_mutation",
        "public_download",
        "public_bucket",
        "partial_export",
    ):
        _require(record.get(forbidden) is False, f"Freeze enables forbidden capability: {forbidden}")
    _require(record.get("next_allowed_stage") == "NEX-P2-10", "Freeze next stage drift")


def validate_workflow() -> None:
    workflow = (ROOT / ".github/workflows/portfolio-api-export.yml").read_text(encoding="utf-8")
    for marker in (
        "python3 scripts/verify_paper_shadow_projection.py",
        "python3 scripts/verify_portfolio_api_export.py",
        "python3 -m unittest discover -s tests -v",
        "uv run ruff format --check",
        "uv run ruff check",
        "uv run mypy",
        'uv run pytest -m "not integration" -q',
        "uv run alembic upgrade head",
        "uv run pytest apps/server/tests/test_postgresql_integration.py -m integration -q",
        "uv run alembic check",
    ):
        _require(marker in workflow, f"P2-09 workflow evidence missing: {marker}")


def main() -> int:
    validate_frozen_p2_08()
    contract = load_contract()
    freeze_record = load_freeze_record()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-09 contract checksum drift")
    validate_runtime_markers()
    validate_freeze_record(freeze_record, contract)
    validate_workflow()
    print("NEX_P2_08_PREREQUISITE=PASS")
    print("NEX_P2_09_PORTFOLIO_API_EXPORT=PASS")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print(f"p2_08_freeze_checksum={P2_08_FREEZE_CHECKSUM}")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print("NEX_P2_09_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
