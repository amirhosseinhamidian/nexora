#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-nav-pnl-performance.json"
P2_06_VERIFIER_PATH = ROOT / "scripts/verify_valuation_evidence.py"
P2_06_FREEZE_PATH = ROOT / "artifacts/p2-06/valuation-evidence-freeze.json"
P2_06_FREEZE_COMMIT = "6b5b696a8d370c6aed6fb47fb22c02407f89b450"
P2_06_CANDIDATE_COMMIT = "f88bf5f7f24ae807bb8d6820ea5e99e872af5224"
P2_06_FREEZE_CHECKSUM = "d3d0eb9e155b210cf6d7e4a824f3b7ed5ceeacd04bae28ae7196d3f369de9f92"
CONTRACT_CHECKSUM = "a38a42e10066b7d1276f988883c0cc54f48483833bcea7b04231a048881b563b"
EXPECTED_OPERATIONS = {
    "GET /v1/portfolios/{portfolio_id}/analytics",
    "GET /v1/portfolios/{portfolio_id}/performance",
}


class NavPnlPerformanceContractError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise NavPnlPerformanceContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.relative_to(ROOT)} must contain an object")
    return payload


def canonical_checksum(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p2_06() -> None:
    spec = importlib.util.spec_from_file_location("verify_valuation_evidence", P2_06_VERIFIER_PATH)
    _require(spec is not None and spec.loader is not None, "unable to load P2-06 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contract = module.load_contract()
    freeze = module.load_freeze_record()
    module.validate_frozen_p2_05()
    module.validate_contract(contract)
    module.validate_runtime_markers()
    module.validate_freeze_record(freeze, contract)
    module.validate_freeze_workflow()
    _require(canonical_checksum(freeze) == P2_06_FREEZE_CHECKSUM, "P2-06 Freeze checksum drift")
    _require(freeze.get("candidate_commit_sha") == P2_06_CANDIDATE_COMMIT, "P2-06 candidate drift")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(
        contract.get("schema_version") == "nexora-nav-pnl-performance-contract-v1",
        "invalid analytics contract schema",
    )
    _require(contract.get("decision_id") == "NEX-P2-07", "invalid analytics decision")
    _require(contract.get("status") == "candidate", "P2-07 must remain a candidate before Freeze")
    prerequisite = contract.get("prerequisite")
    _require(isinstance(prerequisite, dict), "prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-06", "P2-06 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P2-06 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_06_FREEZE_COMMIT, "P2-06 Freeze SHA drift")
    _require(prerequisite.get("accepted_candidate_commit_sha") == P2_06_CANDIDATE_COMMIT, "candidate SHA drift")
    _require(prerequisite.get("freeze_record_checksum") == P2_06_FREEZE_CHECKSUM, "Freeze checksum drift")

    scope = contract.get("scope")
    _require(isinstance(scope, dict), "scope must be an object")
    _require(
        set(scope.get("entities", []))
        == {"point_in_time_nav", "realized_pnl", "unrealized_pnl", "bounded_performance_series"},
        "analytics entity inventory drift",
    )
    for excluded in ("paper_shadow_projection_included", "tax_advice_included", "financial_advice_included"):
        _require(scope.get(excluded) is False, f"P2-07 cannot enable {excluded}")

    policy = contract.get("calculation_policy")
    _require(isinstance(policy, dict), "calculation policy must be an object")
    for required in (
        "historical_holdings_rebuilt_from_journal_at_or_before_as_of",
        "exact_decimal_arithmetic",
        "binary_float_forbidden",
        "nav_is_null_when_any_position_is_unpriced",
        "priced_value_remains_visible_when_nav_is_incomplete",
        "unrealized_pnl_requires_known_basis_and_valuation",
        "realized_pnl_requires_sell_base_proceeds_and_known_consumed_basis",
        "non_sell_disposals_do_not_claim_realized_pnl",
        "missing_and_stale_states_are_visible",
        "unavailable_subperiod_breaks_cumulative_chain",
    ):
        _require(policy.get(required) is True, f"calculation policy requires {required}")
    _require(policy.get("performance_point_minimum") == 2, "performance minimum drift")
    _require(policy.get("performance_point_maximum") == 32, "performance maximum drift")
    _require(policy.get("performance_range_maximum_days") == 366, "performance range drift")

    resolution = contract.get("valuation_resolution")
    _require(isinstance(resolution, dict), "valuation resolution must be an object")
    _require(
        resolution.get("precedence")
        == [
            "base_asset_identity",
            "direct_price_observation",
            "direct_fx_rate_for_fiat",
            "price_observation_plus_one_direct_fx_hop",
            "portfolio_manual_valuation",
            "missing",
        ],
        "valuation precedence drift",
    )
    for forbidden in ("implicit_fx_inversion", "multi_hop_fx_graph", "interpolation", "silent_forward_fill"):
        _require(resolution.get(forbidden) is False, f"forbidden valuation behavior enabled: {forbidden}")

    persistence = contract.get("persistence")
    _require(isinstance(persistence, dict), "persistence policy must be an object")
    _require(persistence.get("derived_on_demand_from_immutable_journal_and_evidence") is True, "lineage drift")
    _require(persistence.get("new_tables") == [], "P2-07 cannot add mutable analytics tables")
    _require(persistence.get("new_migration_required") is False, "unexpected migration requirement")

    runtime = contract.get("runtime_api")
    _require(isinstance(runtime, dict), "runtime API must be an object")
    _require(set(runtime.get("operations", [])) == EXPECTED_OPERATIONS, "analytics API inventory drift")
    _require(runtime.get("owner_id_accepted_from_request") is False, "owner override enabled")
    _require(runtime.get("read_only") is True, "analytics API must remain read-only")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security boundary must be an object")
    _require(all(value is False for value in security.values()), "forbidden capability enabled")
    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("next_allowed_stage") == "NEX-P2-07-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P2-08", "post-Freeze stage drift")
    _require(transition.get("freeze_before_paper_shadow_projection") is True, "Freeze boundary missing")


def validate_runtime_markers() -> None:
    domain = (ROOT / "apps/server/src/nexora/performance.py").read_text(encoding="utf-8")
    repository = (ROOT / "apps/server/src/nexora/adapters/postgresql/performance.py").read_text(encoding="utf-8")
    api = (ROOT / "apps/server/src/nexora/api.py").read_text(encoding="utf-8")
    composition = (ROOT / "apps/server/src/nexora/composition.py").read_text(encoding="utf-8")
    for marker in (
        "class PortfolioAnalyticsSnapshot",
        "class PerformanceSeries",
        "calculate_performance_points",
        "bounded_series_times",
    ):
        _require(marker in domain, f"domain marker missing: {marker}")
    for marker in (
        "class PortfolioPerformanceRepository",
        "def snapshot(",
        "def performance_series(",
        "price.price * fx.rate",
    ):
        _require(marker in repository, f"repository marker missing: {marker}")
    for operation in EXPECTED_OPERATIONS:
        _require(operation.split(" ", 1)[1] in api, f"API route missing: {operation}")
    _require("portfolio_performance_repository" in composition, "analytics repository is not composed")


def validate_workflow() -> None:
    workflow = (ROOT / ".github/workflows/nav-pnl-performance.yml").read_text(encoding="utf-8")
    for marker in (
        "python3 scripts/verify_valuation_evidence.py",
        "python3 scripts/verify_nav_pnl_performance.py",
        'uv run pytest -m "not integration" -q',
        "uv run pytest apps/server/tests/test_postgresql_integration.py -m integration -q",
        "uv run alembic check",
    ):
        _require(marker in workflow, f"workflow marker missing: {marker}")


def main() -> int:
    contract = load_contract()
    validate_frozen_p2_06()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-07 contract checksum drift")
    validate_runtime_markers()
    validate_workflow()
    print("NEX_P2_07_NAV_PNL_PERFORMANCE=PASS")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print(f"p2_06_freeze_checksum={P2_06_FREEZE_CHECKSUM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
