#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-holdings-lots-cost-basis.json"
P2_04_VERIFIER_PATH = ROOT / "scripts/verify_import_reconciliation.py"
P2_04_FREEZE_PATH = ROOT / "artifacts/p2-04/import-reconciliation-freeze.json"
P2_04_FREEZE_COMMIT = "751ada7dc4226745e894fdc630b8d2e92eff1f36"
P2_04_CANDIDATE_COMMIT = "8e1f59f4084f902b4917d91f6ee9593217dbca1e"
P2_04_FREEZE_CHECKSUM = "facbffd3a5a3faf9783b990383919cce936c4b52a28b201a6cca891e39a4ef77"
CONTRACT_CHECKSUM = "bf267ecd8d983a97b30c75f4e4ec54813f73cc5b3fdee86ef4e418d0e6d6e555"
EXPECTED_OPERATIONS = {
    "POST /v1/portfolios/{portfolio_id}/holdings/rebuilds",
    "GET /v1/portfolios/{portfolio_id}/holdings",
    "GET /v1/portfolios/{portfolio_id}/lots",
}
FORBIDDEN_CAPABILITIES = {
    "raw_exchange_credentials",
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
    "financial_advice",
    "tax_advice",
}


class HoldingsProjectionContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HoldingsProjectionContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p2_04() -> None:
    spec = importlib.util.spec_from_file_location("verify_import_reconciliation", P2_04_VERIFIER_PATH)
    _require(spec is not None and spec.loader is not None, "unable to load P2-04 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_p2_03()
    contract = module.load_contract()
    freeze = module.load_freeze_record()
    module.validate_contract(contract)
    module.validate_runtime_markers()
    module.validate_freeze_record(freeze, contract)
    module.validate_freeze_workflow()
    _require(canonical_checksum(freeze) == P2_04_FREEZE_CHECKSUM, "P2-04 Freeze checksum drift")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-holdings-lots-cost-basis-contract-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P2-05", "invalid decision")
    _require(contract.get("decision_date") == "2026-11-01", "invalid decision date")
    _require(contract.get("status") == "candidate", "P2-05 must remain candidate before Freeze")

    prerequisite = contract.get("prerequisite")
    _require(isinstance(prerequisite, dict), "prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-04", "P2-04 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P2-04 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_04_FREEZE_COMMIT, "P2-04 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_04_CANDIDATE_COMMIT,
        "P2-04 candidate drift",
    )
    _require(
        prerequisite.get("freeze_record_path") == P2_04_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-04 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_04_FREEZE_CHECKSUM, "P2-04 checksum drift")

    scope = contract.get("scope")
    _require(isinstance(scope, dict), "scope must be an object")
    _require(set(scope.get("cost_basis_methods", [])) == {"fifo", "weighted_average"}, "method drift")
    _require(len(scope.get("entities", [])) == 5, "entity inventory drift")
    for deferred in (
        "valuation_included",
        "nav_included",
        "realized_pnl_included",
        "unrealized_pnl_included",
        "tax_advice_included",
    ):
        _require(scope.get(deferred) is False, f"P2-05 cannot include {deferred}")

    invariants = contract.get("projection_invariants")
    _require(isinstance(invariants, dict), "projection_invariants must be an object")
    for invariant in (
        "immutable_journal_is_source_of_truth",
        "projection_is_fully_rebuildable",
        "deterministic_journal_order",
        "journal_sha256_checkpoint",
        "explicit_projection_version",
        "exact_decimal_arithmetic",
        "binary_float_forbidden",
        "idempotent_same_journal_rebuild",
        "atomic_projection_replacement",
        "owned_account_transfer_retains_basis",
        "owned_account_transfer_is_not_disposal",
        "negative_holding_rejected",
        "negative_holding_issue_append_only",
        "unknown_basis_remains_visible",
        "owner_scope_required",
    ):
        _require(invariants.get(invariant) is True, f"projection invariant requires {invariant}")

    policy = contract.get("cost_basis_policy")
    _require(isinstance(policy, dict), "cost_basis_policy must be an object")
    for required in (
        "fifo_consumes_oldest_lots_first",
        "weighted_average_consumes_pool_proportionally",
        "half_even_rounding",
        "asset_precision_required",
        "rounding_remainder_preserved",
        "missing_cost_evidence_cannot_be_invented",
    ):
        _require(policy.get(required) is True, f"cost-basis policy requires {required}")
    _require(policy.get("jurisdiction_specific_tax_logic") is False, "tax logic must remain deferred")

    persistence = contract.get("persistence")
    _require(isinstance(persistence, dict), "persistence must be an object")
    _require(persistence.get("migration_revision") == "20261101_0009", "migration revision drift")
    _require(len(persistence.get("tables", [])) == 5, "persistence table inventory drift")
    for required in (
        "derived_rows_replaceable",
        "rejection_evidence_immutable",
        "composite_owner_foreign_keys",
        "upgrade_downgrade_rebuild_drift_cycle_required",
    ):
        _require(persistence.get(required) is True, f"persistence requires {required}")

    runtime = contract.get("runtime_api")
    _require(isinstance(runtime, dict), "runtime_api must be an object")
    _require(runtime.get("authentication") == "opaque_owner_session", "authentication drift")
    _require(runtime.get("owner_id_accepted_from_request") is False, "owner override is forbidden")
    _require(runtime.get("csrf_for_rebuild") is True, "CSRF protection is required")
    _require(runtime.get("decimal_values_encoded_as_strings") is True, "decimal string encoding is required")
    _require(set(runtime.get("operations", [])) == EXPECTED_OPERATIONS, "API operation inventory drift")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security_boundary must be an object")
    _require(set(security) == FORBIDDEN_CAPABILITIES, "security capability inventory drift")
    for capability in FORBIDDEN_CAPABILITIES:
        _require(security.get(capability) is False, f"forbidden capability enabled: {capability}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_candidate") is True, "P2-05 is not ready for candidate")
    _require(transition.get("next_allowed_stage") == "NEX-P2-05-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P2-06", "post-Freeze stage drift")
    _require(transition.get("freeze_before_valuation") is True, "valuation must remain blocked")


def validate_runtime_markers() -> None:
    paths = {
        "domain": ROOT / "apps/server/src/nexora/holdings_projection.py",
        "repository": ROOT / "apps/server/src/nexora/adapters/postgresql/holdings_projection.py",
        "models": ROOT / "apps/server/src/nexora/adapters/postgresql/models.py",
        "migration": ROOT / "alembic/versions/20261101_0009_holdings_lots_cost_basis.py",
        "api": ROOT / "apps/server/src/nexora/api.py",
    }
    content = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    for marker in ("class CostBasisMethod", "def journal_checksum", "def rebuild_projection", "ROUND_HALF_EVEN"):
        _require(marker in content["domain"], f"missing domain marker: {marker}")
    for marker in ("class HoldingsProjectionRepository", "def rebuild", "def _record_rejection"):
        _require(marker in content["repository"], f"missing repository marker: {marker}")
    for marker in (
        "class HoldingsRebuildRecord",
        "class HoldingProjectionRecord",
        "class LotProjectionRecord",
        "class LotConsumptionRecord",
        "class HoldingsRebuildIssueRecord",
    ):
        _require(marker in content["models"], f"missing persistence marker: {marker}")
    _require('revision: str = "20261101_0009"' in content["migration"], "migration marker missing")
    _require("trg_holdings_rebuild_issues_immutable" in content["migration"], "immutable issue trigger missing")
    for operation in EXPECTED_OPERATIONS:
        _require(f'"{operation.split(" ", 1)[1]}"' in content["api"], f"missing API operation: {operation}")
    openapi = _json(ROOT / "contracts/runtime/v1/openapi.json")
    operations = {
        f"{method.upper()} {path}"
        for path, item in openapi["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    _require(operations >= EXPECTED_OPERATIONS, "P2-05 OpenAPI operation inventory drift")


def main() -> int:
    validate_frozen_p2_04()
    contract = load_contract()
    validate_contract(contract)
    validate_runtime_markers()
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-05 contract checksum drift")
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P2_04_PREREQUISITE=PASS")
    print("NEX_P2_05_HOLDINGS_PROJECTION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
