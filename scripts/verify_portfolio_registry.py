#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-portfolio-registry.json"
P2_01_CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-two-portfolio-domain.json"
P2_01_FREEZE_PATH = ROOT / "artifacts/p2-01/portfolio-domain-roadmap-freeze.json"
P2_01_VERIFIER_PATH = ROOT / "scripts/verify_phase_two_portfolio_domain.py"
P2_01_FREEZE_COMMIT = "e82731b9ab50ca7ca0911250f71bf9096a89b314"
P2_01_CANDIDATE_COMMIT = "5fad7e9f49a48fb3068634ee8ae6621af8cc6ec1"
P2_01_FREEZE_CHECKSUM = "ab48298be9ba8b7ddb66b9857f191d64f123499d0ef4ac494f065bc16b8c6515"
CONTRACT_CHECKSUM = "9db27575f9969359d5e29c7990a988320a4e8742d12cfebac3625fad18d1d42d"

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


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
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


def main() -> int:
    validate_frozen_p2_01()
    contract = load_contract()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-02 contract checksum drift")
    validate_runtime_markers()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P2_01_PREREQUISITE=PASS")
    print("NEX_P2_02_PORTFOLIO_REGISTRY=PASS")
    print("NEX_P2_02_READY_FOR_CANDIDATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
