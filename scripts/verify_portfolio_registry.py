#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-portfolio-registry.json"
FREEZE_PATH = ROOT / "artifacts/p2-02/portfolio-registry-freeze.json"
P2_01_CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-two-portfolio-domain.json"
P2_01_FREEZE_PATH = ROOT / "artifacts/p2-01/portfolio-domain-roadmap-freeze.json"
P2_01_VERIFIER_PATH = ROOT / "scripts/verify_phase_two_portfolio_domain.py"
P2_01_FREEZE_COMMIT = "e82731b9ab50ca7ca0911250f71bf9096a89b314"
P2_01_CANDIDATE_COMMIT = "5fad7e9f49a48fb3068634ee8ae6621af8cc6ec1"
P2_01_FREEZE_CHECKSUM = "ab48298be9ba8b7ddb66b9857f191d64f123499d0ef4ac494f065bc16b8c6515"
CONTRACT_CHECKSUM = "9db27575f9969359d5e29c7990a988320a4e8742d12cfebac3625fad18d1d42d"
CANDIDATE_SHA = "add7a7eec7226ecc62989b23cccf380c32e678d7"
CANDIDATE_TREE_SHA = "68bc364bd2950f33084394c0d7715d0ec4e179b2"
CANDIDATE_MESSAGE = "test(nexora): isolate retention test from host disk capacity"
CANDIDATE_PREDECESSOR = "8783e72b4e496af9f66ff63925595140e76716ed"
CANDIDATE_LINEAGE_CHECKSUM = "3e6443affddd60670ffb06d4e638ce1b33cd41b56351fbf0c24d148a5c99288e"
WORKFLOW_RUNS_CHECKSUM = "11b685926e17f028d7b44f9a636bf74a6b3b618734f9609ce83e008076cabba9"
CHECKS_CHECKSUM = "fb67b369b3d88ba9f0167ed1fea65123a96725488af48595aba5f5d85d367f05"
EXPECTED_WORKFLOW_RUNS = 17
EXPECTED_CHECKS = 57

EXPECTED_ENTITIES = {"asset", "asset_identifier", "portfolio", "account"}
EXPECTED_TABLES = {
    "nexora.assets",
    "nexora.asset_identifiers",
    "nexora.portfolios",
    "nexora.accounts",
}
EXPECTED_OPERATIONS = {
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
FORBIDDEN_CAPABILITIES = {
    "transaction_journal",
    "exchange_credentials",
    "wallet_private_keys",
    "wallet_seed_phrases",
    "wallet_signing",
    "fund_transfer",
    "live_orders",
    "direct_trd_bot_database_access",
    "multi_user",
    "saas",
    "autonomous_ai_execution",
    "ml_training_or_inference",
}


class PortfolioRegistryContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PortfolioRegistryContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p2_01() -> None:
    spec = importlib.util.spec_from_file_location("verify_phase_two_portfolio_domain", P2_01_VERIFIER_PATH)
    _require(spec is not None and spec.loader is not None, "unable to load P2-01 verifier")
    if spec is None or spec.loader is None:
        raise PortfolioRegistryContractError("unable to load P2-01 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contract = module.load_contract(P2_01_CONTRACT_PATH)
    freeze = module.load_freeze_record(P2_01_FREEZE_PATH)
    module.validate_phase_one_prerequisite()
    module.validate_contract(contract)
    module.validate_freeze_record(freeze, contract)
    _require(canonical_checksum(freeze) == P2_01_FREEZE_CHECKSUM, "P2-01 Freeze artifact drift")
    _require(freeze.get("frozen") is True, "P2-01 is not frozen")
    _require(freeze.get("next_allowed_stage") == "NEX-P2-02", "P2-01 does not open P2-02")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-portfolio-registry-contract-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P2-02", "invalid decision")
    _require(contract.get("decision_date") == "2026-10-31", "invalid decision date")
    _require(contract.get("status") == "candidate", "P2-02 must remain a candidate before Freeze")

    prerequisite = contract.get("prerequisite")
    _require(isinstance(prerequisite, dict), "prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-01", "P2-01 prerequisite drift")
    _require(prerequisite.get("freeze_commit_sha") == P2_01_FREEZE_COMMIT, "P2-01 Freeze commit drift")
    _require(prerequisite.get("accepted_candidate_commit_sha") == P2_01_CANDIDATE_COMMIT, "P2-01 candidate drift")
    _require(prerequisite.get("artifact_checksum") == P2_01_FREEZE_CHECKSUM, "P2-01 Freeze checksum drift")
    _require(prerequisite.get("frozen") is True, "P2-01 prerequisite must be frozen")

    scope = contract.get("scope")
    _require(isinstance(scope, dict), "scope must be an object")
    _require(scope.get("owner_model") == "single_owner_session_derived", "owner model drift")
    _require(set(scope.get("entities", [])) == EXPECTED_ENTITIES, "entity inventory drift")
    _require(scope.get("physical_delete_exposed") is False, "physical delete cannot be exposed")
    for key in ("transaction_journal_included", "holdings_projection_included", "valuation_included"):
        _require(scope.get(key) is False, f"P2-02 cannot include {key}")

    assets = contract.get("asset_registry")
    _require(isinstance(assets, dict), "asset_registry must be an object")
    _require(
        set(assets.get("classes", [])) == {"crypto", "fiat", "equity", "fund", "commodity", "other"},
        "asset class drift",
    )
    _require(assets.get("precision_range") == [0, 30], "asset precision drift")
    _require(assets.get("statuses") == ["active", "inactive"], "asset lifecycle drift")
    _require(assets.get("identifier_unique_per_owner_scheme_value") is True, "identifier uniqueness is required")

    portfolios = contract.get("portfolio_registry")
    _require(isinstance(portfolios, dict), "portfolio_registry must be an object")
    _require(set(portfolios.get("kinds", [])) == {"personal", "paper", "shadow"}, "portfolio kind drift")
    _require(portfolios.get("statuses") == ["active", "archived"], "portfolio lifecycle drift")
    _require(portfolios.get("active_owner_scoped_base_asset_required") is True, "base asset boundary is required")

    accounts = contract.get("account_registry")
    _require(isinstance(accounts, dict), "account_registry must be an object")
    _require(accounts.get("statuses") == ["active", "closed"], "account lifecycle drift")
    _require(accounts.get("active_owner_scoped_portfolio_required") is True, "account owner boundary is required")
    _require(accounts.get("credentials_supported") is False, "account credentials are forbidden")
    _require(accounts.get("wallet_signing_material_supported") is False, "wallet signing material is forbidden")

    persistence = contract.get("persistence")
    _require(isinstance(persistence, dict), "persistence must be an object")
    _require(persistence.get("migration_revision") == "20261031_0006", "migration revision drift")
    _require(set(persistence.get("tables", [])) == EXPECTED_TABLES, "table inventory drift")
    for key in (
        "owner_scope_on_every_table",
        "composite_owner_foreign_keys",
        "timezone_aware_timestamps",
        "row_version_on_lifecycle_roots",
        "database_constraints_required",
        "upgrade_downgrade_rebuild_drift_cycle_required",
    ):
        _require(persistence.get(key) is True, f"persistence requires {key}")

    runtime = contract.get("runtime_api")
    _require(isinstance(runtime, dict), "runtime_api must be an object")
    _require(runtime.get("authentication") == "opaque_owner_session", "authentication drift")
    _require(runtime.get("owner_id_accepted_from_request") is False, "request owner override is forbidden")
    _require(runtime.get("csrf_for_mutations") is True, "CSRF protection is required")
    _require(runtime.get("unknown_fields_rejected") is True, "unknown fields must be rejected")
    _require(set(runtime.get("operations", [])) == EXPECTED_OPERATIONS, "API operation inventory drift")
    _require(runtime.get("lifecycle_mutations_require_expected_row_version") is True, "row version is required")

    forbidden = contract.get("forbidden_capabilities")
    _require(isinstance(forbidden, dict), "forbidden_capabilities must be an object")
    _require(set(forbidden) == FORBIDDEN_CAPABILITIES, "forbidden capability inventory drift")
    for capability in FORBIDDEN_CAPABILITIES:
        _require(forbidden.get(capability) is False, f"forbidden capability enabled: {capability}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("next_allowed_stage") == "NEX-P2-02-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P2-03", "post-Freeze stage drift")
    _require(transition.get("freeze_before_transaction_journal") is True, "P2-03 must remain blocked")


def validate_runtime_markers() -> None:
    models = (ROOT / "apps/server/src/nexora/adapters/postgresql/models.py").read_text(encoding="utf-8")
    repository = (ROOT / "apps/server/src/nexora/adapters/postgresql/portfolio_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "apps/server/src/nexora/api.py").read_text(encoding="utf-8")
    migration = (ROOT / "alembic/versions/20261031_0006_portfolio_asset_account_registry.py").read_text(
        encoding="utf-8"
    )
    for marker in ("class AssetRecord", "class AssetIdentifierRecord", "class PortfolioRecord", "class AccountRecord"):
        _require(marker in models, f"missing database model: {marker}")
    for marker in ("def create_asset", "def create_portfolio", "def create_account", "expected_row_version"):
        _require(marker in repository, f"missing repository marker: {marker}")
    for operation in ("/v1/assets", "/v1/portfolios", "/v1/accounts"):
        _require(operation in api, f"missing API route: {operation}")
    _require('revision: str = "20261031_0006"' in migration, "migration revision marker drift")
    _require("transactions" not in {table.split(".")[-1] for table in EXPECTED_TABLES}, "journal entered P2-02")
    openapi = _json(ROOT / "contracts/runtime/v1/openapi.json")
    operations = {
        f"{method.upper()} {path}"
        for path, path_item in openapi["paths"].items()
        for method in path_item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    _require(operations >= EXPECTED_OPERATIONS, "P2-02 OpenAPI operation inventory drift")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-portfolio-registry-freeze-v1", "invalid Freeze schema")
    _require(record.get("decision_id") == "NEX-P2-02", "invalid Freeze decision")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "Freeze repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_tree_sha") == CANDIDATE_TREE_SHA, "candidate tree drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "candidate message drift")
    _require(record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR, "candidate predecessor drift")

    lineage = record.get("candidate_lineage")
    _require(isinstance(lineage, list), "candidate lineage must be an array")
    _require(len(lineage) == 3, "candidate lineage must contain all three P2-02 commits")
    _require(canonical_checksum(lineage) == CANDIDATE_LINEAGE_CHECKSUM, "candidate lineage drift")
    _require(lineage[-1].get("sha") == CANDIDATE_SHA, "candidate lineage does not end at accepted SHA")

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
        record.get("check_summary") == {"total": 57, "successful": 57, "failed": 0, "pending": 0},
        "check summary drift",
    )

    contract_evidence = record.get("portfolio_registry_contract")
    _require(isinstance(contract_evidence, dict), "portfolio registry evidence must be an object")
    _require(
        contract_evidence.get("schema_version") == contract.get("schema_version"),
        "portfolio registry schema drift",
    )
    _require(contract_evidence.get("path") == CONTRACT_PATH.relative_to(ROOT).as_posix(), "contract path drift")
    _require(contract_evidence.get("checksum") == canonical_checksum(contract), "contract evidence drift")
    _require(contract_evidence.get("checksum") == CONTRACT_CHECKSUM, "contract checksum drift")

    prerequisite = record.get("p2_01_prerequisite")
    _require(isinstance(prerequisite, dict), "P2-01 prerequisite evidence must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-01", "P2-01 decision drift")
    _require(prerequisite.get("frozen") is True, "P2-01 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_01_FREEZE_COMMIT, "P2-01 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_01_CANDIDATE_COMMIT,
        "P2-01 candidate drift",
    )
    _require(
        prerequisite.get("freeze_record_path") == P2_01_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-01 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_01_FREEZE_CHECKSUM, "P2-01 checksum drift")

    _require(record.get("recorded_on") == "2026-10-31", "Freeze record date drift")
    _require(record.get("frozen") is True, "P2-02 must be frozen")
    _require(record.get("portfolio_registry_complete") is True, "registry completion evidence missing")
    _require(record.get("portfolio_product_complete") is False, "portfolio product completion cannot be claimed")
    _require(record.get("transaction_journal_implemented") is False, "transaction journal entered P2-02")
    _require(record.get("production_readiness_claimed") is False, "production readiness cannot be claimed")
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
        "direct_trd_bot_database_access",
    ):
        _require(record.get(forbidden) is False, f"Freeze enables forbidden capability: {forbidden}")
    _require(record.get("next_allowed_stage") == "NEX-P2-03", "Freeze next stage drift")


def validate_freeze_workflow() -> None:
    workflow = (ROOT / ".github/workflows/portfolio-registry.yml").read_text(encoding="utf-8")
    for marker in (
        "Verify frozen P2-01 prerequisite",
        "Verify P2-02 registry contract",
        "python3 -m unittest discover -s tests -v",
        "uv run ruff format --check",
        "uv run ruff check",
        "uv run mypy",
        'uv run pytest -m "not integration" -q',
        "uv run alembic upgrade head",
        "uv run pytest apps/server/tests/test_postgresql_integration.py -m integration -q",
        "uv run alembic downgrade base",
        "uv run alembic check",
    ):
        _require(marker in workflow, f"P2-02 workflow evidence missing: {marker}")


def main() -> int:
    validate_frozen_p2_01()
    contract = load_contract()
    freeze_record = load_freeze_record()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-02 contract checksum drift")
    validate_runtime_markers()
    validate_freeze_record(freeze_record, contract)
    validate_freeze_workflow()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P2_01_PREREQUISITE=PASS")
    print("NEX_P2_02_PORTFOLIO_REGISTRY=PASS")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print("NEX_P2_02_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
