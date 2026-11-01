#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-price-fx-manual-valuation.json"
P2_05_VERIFIER_PATH = ROOT / "scripts/verify_holdings_projection.py"
CONTRACT_CHECKSUM = "3d3de09ac85d60b1701618d423e5d5d5ebec1fc1fdb7948da3960eda29edc67a"

EXPECTED_OPERATIONS = {
    "POST /v1/valuation/price-observations",
    "GET /v1/valuation/price-observations",
    "POST /v1/valuation/fx-rate-observations",
    "GET /v1/valuation/fx-rate-observations",
    "POST /v1/valuation/manual-valuations",
    "GET /v1/valuation/manual-valuations",
    "GET /v1/portfolios/{portfolio_id}/valuation-status",
}
EXPECTED_TABLES = {
    "nexora.price_observations",
    "nexora.fx_rate_observations",
    "nexora.manual_valuations",
}


class ValuationEvidenceContractError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValuationEvidenceContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.relative_to(ROOT)} must contain an object")
    return payload


def canonical_checksum(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p2_05() -> None:
    spec = importlib.util.spec_from_file_location("verify_holdings_projection", P2_05_VERIFIER_PATH)
    _require(spec is not None and spec.loader is not None, "unable to load P2-05 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contract = module.load_contract()
    freeze = module.load_freeze_record()
    module.validate_frozen_p2_04()
    module.validate_contract(contract)
    module.validate_runtime_markers()
    module.validate_freeze_record(freeze, contract)
    module.validate_freeze_workflow()


def validate_contract(contract: dict[str, Any]) -> None:
    _require(
        contract.get("schema_version") == "nexora-price-fx-manual-valuation-contract-v1",
        "invalid valuation contract schema",
    )
    _require(contract.get("decision_id") == "NEX-P2-06", "invalid valuation decision")
    _require(contract.get("status") == "candidate", "P2-06 must remain a candidate before Freeze")
    prerequisite = contract.get("prerequisite")
    _require(isinstance(prerequisite, dict), "prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-05", "P2-05 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P2-05 prerequisite must be frozen")
    _require(
        prerequisite.get("freeze_commit_sha") == "bddee3b638e67d25aaeaa1b754352b78579e5d2a",
        "P2-05 Freeze SHA drift",
    )

    scope = contract.get("scope")
    _require(isinstance(scope, dict), "scope must be an object")
    _require(
        set(scope.get("entities", []))
        == {"price_observation", "fx_rate_observation", "manual_valuation", "valuation_status"},
        "valuation entity inventory drift",
    )
    for excluded in (
        "nav_included",
        "realized_pnl_included",
        "unrealized_pnl_included",
        "performance_included",
        "tax_advice_included",
        "financial_advice_included",
    ):
        _require(scope.get(excluded) is False, f"P2-06 cannot enable {excluded}")

    invariants = contract.get("evidence_invariants")
    _require(isinstance(invariants, dict), "evidence invariants must be an object")
    for required in (
        "price_observation_immutable",
        "fx_rate_observation_immutable",
        "manual_valuation_immutable",
        "manual_valuation_requires_reason",
        "owner_scope_required",
        "source_lineage_required",
        "source_payload_sha256_required",
        "idempotency_required",
        "canonical_request_sha256_required",
        "utc_evidence_time_required",
        "explicit_valid_until_required",
        "exact_decimal_arithmetic",
        "binary_float_forbidden",
        "positive_values_required",
        "fx_assets_must_be_fiat",
        "manual_quote_matches_portfolio_base",
        "future_evidence_excluded",
        "no_silent_forward_fill",
        "no_interpolation",
        "stale_evidence_visible",
        "missing_evidence_visible",
        "deterministic_latest_at_or_before",
    ):
        _require(invariants.get(required) is True, f"valuation invariant requires {required}")

    precedence = contract.get("evidence_precedence")
    _require(isinstance(precedence, dict), "evidence precedence must be an object")
    _require(
        precedence.get("order") == ["direct_price_observation", "portfolio_manual_valuation", "missing"],
        "evidence precedence drift",
    )
    _require(precedence.get("stale_direct_price_remains_selected_and_visible") is True, "stale evidence hidden")
    _require(precedence.get("manual_never_overwrites_observation") is True, "manual evidence may overwrite")
    _require(precedence.get("fx_cross_conversion_deferred_to_p2_07") is True, "P2-07 scope entered P2-06")

    persistence = contract.get("persistence")
    _require(isinstance(persistence, dict), "persistence must be an object")
    _require(persistence.get("migration_revision") == "20261101_0010", "migration revision drift")
    _require(set(persistence.get("tables", [])) == EXPECTED_TABLES, "valuation table inventory drift")
    _require(persistence.get("append_only_trigger_required") is True, "append-only enforcement missing")
    _require((persistence.get("numeric_precision"), persistence.get("numeric_scale")) == (60, 30), "decimal drift")

    runtime = contract.get("runtime_api")
    _require(isinstance(runtime, dict), "runtime API must be an object")
    _require(set(runtime.get("operations", [])) == EXPECTED_OPERATIONS, "valuation API inventory drift")
    _require(runtime.get("owner_id_accepted_from_request") is False, "owner override enabled")
    _require(runtime.get("csrf_for_writes") is True, "CSRF protection missing")
    _require(runtime.get("update_delete_operations") is False, "valuation mutation route enabled")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security boundary must be an object")
    _require(all(value is False for value in security.values()), "forbidden capability enabled")
    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("next_allowed_stage") == "NEX-P2-06-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P2-07", "post-Freeze stage drift")
    _require(transition.get("freeze_before_nav_and_pnl") is True, "NAV/P&L Freeze boundary missing")


def validate_runtime_markers() -> None:
    migration = (ROOT / "alembic/versions/20261101_0010_price_fx_manual_valuation.py").read_text(encoding="utf-8")
    models = (ROOT / "apps/server/src/nexora/adapters/postgresql/models.py").read_text(encoding="utf-8")
    repository = (ROOT / "apps/server/src/nexora/adapters/postgresql/valuation.py").read_text(encoding="utf-8")
    api = (ROOT / "apps/server/src/nexora/api.py").read_text(encoding="utf-8")
    composition = (ROOT / "apps/server/src/nexora/composition.py").read_text(encoding="utf-8")
    for table in ("price_observations", "fx_rate_observations", "manual_valuations"):
        _require(table in migration and table in models, f"valuation table marker missing: {table}")
    _require("CREATE TRIGGER trg_{table_name}_immutable" in migration, "append-only trigger creation missing")
    _require(
        '("price_observations", "fx_rate_observations", "manual_valuations")' in migration,
        "append-only table inventory drift",
    )
    for marker in (
        "class ValuationEvidenceRepository",
        "create_price_observation",
        "create_fx_rate_observation",
        "create_manual_valuation",
        "portfolio_status",
    ):
        _require(marker in repository, f"repository marker missing: {marker}")
    for operation in EXPECTED_OPERATIONS:
        path = operation.split(" ", 1)[1]
        _require(path in api, f"API route missing: {operation}")
    _require("valuation_evidence_repository" in composition, "valuation repository is not composed")


def main() -> int:
    validate_frozen_p2_05()
    contract = load_contract()
    validate_contract(contract)
    validate_runtime_markers()
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-06 contract checksum drift")
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P2_05_PREREQUISITE=PASS")
    print("NEX_P2_06_VALUATION_EVIDENCE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
