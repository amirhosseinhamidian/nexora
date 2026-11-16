#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-portfolio-candidate-impact.json"
P3_05_CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-risk-gate-explanation.json"
SERVICE_PATH = ROOT / "apps/server/src/nexora/portfolio_candidate_impact.py"
API_PATH = ROOT / "apps/server/src/nexora/api.py"
WEB_PATH = ROOT / "apps/web/src/components/decision-feed.tsx"


class PortfolioCandidateImpactContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PortfolioCandidateImpactContractError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def validate_prerequisite() -> None:
    prior = load_json(P3_05_CONTRACT_PATH)
    require(prior.get("decision_id") == "NEX-P3-05", "P3-05 decision drift")
    prerequisite = load_contract().get("prerequisites")
    require(isinstance(prerequisite, dict), "P3-06 prerequisite missing")
    require(
        prerequisite.get("p3_05_accepted_commit_sha") == "1ffa8b6dd87ade246c87c40570ab5db27b72094a",
        "accepted P3-05 SHA drift",
    )


def validate_contract(contract: dict[str, Any]) -> None:
    require(
        contract.get("schema_version") == "nexora-portfolio-candidate-impact-contract-v1",
        "schema drift",
    )
    require(contract.get("decision_id") == "NEX-P3-06", "stage ID drift")
    require(contract.get("status") == "candidate", "candidate status drift")
    prerequisite = contract.get("prerequisites")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(prerequisite.get("provider_release") == "0.3.1", "provider release drift")
    require(prerequisite.get("matching_risk_gate_required") is True, "risk prerequisite weakened")

    api = contract.get("api")
    require(isinstance(api, dict), "API contract missing")
    for key in ("authenticated", "owner_scoped", "active_generation_only", "complete_source_reference"):
        require(api.get(key) is True, f"API invariant disabled: {key}")
    require(api.get("staging_generation_visible") is False, "staging generation became visible")
    require(
        api.get("invalid_portfolio_evidence_action") == "unprocessable_fail_closed",
        "portfolio validation no longer fails closed",
    )

    analysis = contract.get("provider_analysis")
    require(isinstance(analysis, dict), "provider analysis missing")
    require(analysis.get("engine_owner") == "trd_bot", "portfolio ownership drift")
    require(
        analysis.get("required_scenario_shocks") == ["-0.100000", "-0.050000", "0.050000", "0.100000"],
        "bounded scenario set drift",
    )
    require(
        analysis.get("required_checks")
        == [
            "portfolio_active",
            "portfolio_capacity",
            "projected_exposure",
            "projected_concentration",
            "candidate_correlation",
            "scenario_loss",
            "regime_alignment",
        ],
        "portfolio check set drift",
    )
    require(
        analysis.get("missing_uncertainty_action") == "explicit_not_supplied",
        "missing uncertainty became implicit",
    )
    require(
        analysis.get("risk_gate_checksum_cross_validated") is True,
        "Risk Gate checksum cross-validation disabled",
    )
    ownership = contract.get("ownership_boundary")
    require(
        isinstance(ownership, dict) and all(value is False for value in ownership.values()),
        "ownership boundary widened",
    )
    web = contract.get("web")
    require(isinstance(web, dict) and all(value is True for value in web.values()), "product states weakened")
    security = contract.get("security_boundary")
    require(isinstance(security, dict) and all(value is False for value in security.values()), "security widened")
    scope = contract.get("scope")
    require(isinstance(scope, dict) and all(value is False for value in scope.values()), "future scope added")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition missing")
    require(
        transition.get("next_allowed_stage_after_ci_acceptance") == "NEX-P3-07",
        "next stage drift",
    )
    require(
        transition.get("requires_cross_resource_risk_lineage_test") is True,
        "cross-resource gate weakened",
    )


def validate_implementation() -> None:
    for path in (SERVICE_PATH, API_PATH, WEB_PATH):
        require(path.is_file(), f"implementation file missing: {path.name}")
    for path in (SERVICE_PATH, API_PATH):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    service = SERVICE_PATH.read_text(encoding="utf-8")
    api = API_PATH.read_text(encoding="utf-8")
    web = WEB_PATH.read_text(encoding="utf-8")
    for marker in (
        "ProviderPortfolioPayload",
        "ProviderRiskGatePayload",
        "EXPECTED_SCENARIO_SHOCKS",
        "EXPECTED_CHECK_NAMES",
        "TRD_BOT_PORTFOLIO_UNCERTAINTY_NOT_SUPPLIED",
        "risk_gate_checksum_cross_validated",
        "transaction_created",
        "order_intent_created",
    ):
        require(marker in service, f"service behavior missing: {marker}")
    require('"/v1/portfolio-impacts/{evaluation_id}"' in api, "portfolio impact route missing")
    for marker in ("portfolioImpact", "analysis.scenarios", "analysis.checks", "Promise.allSettled"):
        require(marker in web, f"Web behavior missing: {marker}")
    combined = service + api + web
    for forbidden in ("exchange_api_key", "wallet_private_key", "fund_transfer(", "submit_order("):
        require(forbidden not in combined, f"forbidden capability present: {forbidden}")


def verify() -> None:
    validate_prerequisite()
    validate_contract(load_contract())
    validate_implementation()


def main() -> int:
    verify()
    print("NEX_P3_05_ACCEPTED_SHA=PASS")
    print("NEX_P3_06_PORTFOLIO_CANDIDATE_IMPACT=PASS")
    print("NEX_P3_06_RISK_GATE_LINEAGE=PASS")
    print("NEX_P3_06_BOUNDED_WHAT_IF=PASS")
    print("NEX_P3_06_PERSONAL_ASSET_BINDING=DEFERRED")
    print("NEX_P3_07=BLOCKED_PENDING_P3_06_CI_ACCEPTANCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
