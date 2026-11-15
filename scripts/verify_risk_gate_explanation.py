#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-risk-gate-explanation.json"
P3_04_CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-decision-feed-candidate-details.json"
SERVICE_PATH = ROOT / "apps/server/src/nexora/risk_gate_explanation.py"
API_PATH = ROOT / "apps/server/src/nexora/api.py"
WEB_PATH = ROOT / "apps/web/src/components/decision-feed.tsx"


class RiskGateExplanationContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RiskGateExplanationContractError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def validate_prerequisite() -> None:
    prior = load_json(P3_04_CONTRACT_PATH)
    require(prior.get("decision_id") == "NEX-P3-04", "P3-04 decision drift")
    transition = prior.get("transition")
    require(isinstance(transition, dict), "P3-04 transition is missing")
    require(transition.get("post_freeze_stage") == "NEX-P3-05", "P3-04 did not preserve P3-05")


def validate_contract(contract: dict[str, Any]) -> None:
    require(
        contract.get("schema_version") == "nexora-risk-gate-explanation-contract-v1",
        "schema drift",
    )
    require(contract.get("decision_id") == "NEX-P3-05", "stage ID drift")
    require(contract.get("status") == "candidate", "candidate status drift")
    prerequisite = contract.get("prerequisites")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(
        prerequisite.get("p3_04_accepted_commit_sha") == "9438dc4c7458b17ca94b6a5efb726fda9a98a37f",
        "accepted P3-04 SHA drift",
    )
    require(prerequisite.get("provider_release") == "0.3.1", "provider release drift")

    api = contract.get("api")
    require(isinstance(api, dict), "API contract missing")
    for key in ("authenticated", "owner_scoped", "active_generation_only", "complete_source_reference"):
        require(api.get(key) is True, f"API invariant disabled: {key}")
    require(api.get("staging_generation_visible") is False, "staging generation became visible")
    require(api.get("invalid_risk_evidence_action") == "unprocessable_fail_closed", "fail-closed drift")

    explanation = contract.get("explanation")
    require(isinstance(explanation, dict), "explanation contract missing")
    require(explanation.get("provider_reason_namespace") == "trd_bot", "provider reason namespace drift")
    for key in (
        "policy_version_visible",
        "policy_checksum_visible",
        "all_provider_reason_codes_preserved",
        "all_provider_checks_preserved_in_order",
        "check_actual_and_limit_values_visible",
        "source_and_evidence_checksums_visible",
    ):
        require(explanation.get(key) is True, f"explanation invariant disabled: {key}")
    require(
        explanation.get("required_provider_checks")
        == ["candidate_fresh", "ranking_score", "reward_risk", "risk_budget", "notional_cap"],
        "provider check set drift",
    )
    require(
        explanation.get("missing_uncertainty_action") == "explicit_not_supplied",
        "missing uncertainty became implicit",
    )
    require(explanation.get("position_sizing_exposed") is False, "position sizing opened early")

    ownership = contract.get("ownership_boundary")
    require(isinstance(ownership, dict), "ownership boundary missing")
    require(ownership.get("risk_engine_owner") == "trd_bot", "risk ownership drift")
    require(
        all(value is False for key, value in ownership.items() if key != "risk_engine_owner"),
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
    require(transition.get("next_allowed_stage") == "NEX-P3-05-FREEZE", "acceptance bypassed")
    require(transition.get("post_freeze_stage") == "NEX-P3-06", "next stage drift")


def validate_implementation() -> None:
    for path in (SERVICE_PATH, API_PATH, WEB_PATH):
        require(path.is_file(), f"implementation file missing: {path.name}")
    for path in (SERVICE_PATH, API_PATH):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    service = SERVICE_PATH.read_text(encoding="utf-8")
    api = API_PATH.read_text(encoding="utf-8")
    web = WEB_PATH.read_text(encoding="utf-8")
    for marker in (
        "ProviderRiskGatePayload",
        "provider_reason_codes",
        "TRD_BOT_RISK_UNCERTAINTY_NOT_SUPPLIED",
        "position_sizing_exposed",
        "DecisionProjectionRecord.model_validate",
    ):
        require(marker in service, f"service behavior missing: {marker}")
    require('"/v1/risk-gates/{evaluation_id}"' in api, "Risk Gate route missing")
    for marker in ("riskGate.policy", "provider_reason_codes", "uncertaintyNotSupplied"):
        require(marker in web, f"Web behavior missing: {marker}")
    combined = service + api + web
    for forbidden in ("live_order", "exchange_api_key", "wallet_private_key", "fund_transfer"):
        require(forbidden not in combined, f"forbidden capability present: {forbidden}")


def verify() -> None:
    validate_prerequisite()
    validate_contract(load_contract())
    validate_implementation()


def main() -> int:
    verify()
    print("NEX_P3_04_ACCEPTED_SHA=PASS")
    print("NEX_P3_05_RISK_GATE_EXPLANATION=PASS")
    print("NEX_P3_05_PROVIDER_REASON_CODES=PASS")
    print("NEX_P3_05_UNCERTAINTY_EXPLICIT=PASS")
    print("NEX_P3_05_RISK_RECOMPUTATION=FORBIDDEN")
    print("NEX_P3_06=BLOCKED_PENDING_P3_05_ACCEPTANCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
