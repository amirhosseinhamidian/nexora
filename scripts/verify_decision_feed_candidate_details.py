#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-decision-feed-candidate-details.json"
P3_03_CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-durable-decision-event-projection.json"
SERVICE_PATH = ROOT / "apps/server/src/nexora/decision_feed.py"
REPOSITORY_PATH = ROOT / "apps/server/src/nexora/adapters/postgresql/decision_projection.py"
API_PATH = ROOT / "apps/server/src/nexora/api.py"
WEB_PATH = ROOT / "apps/web/src/components/decision-feed.tsx"


class DecisionFeedContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DecisionFeedContractError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def validate_prerequisite() -> None:
    prior = load_json(P3_03_CONTRACT_PATH)
    require(prior.get("decision_id") == "NEX-P3-03", "P3-03 decision drift")
    transition = prior.get("transition")
    require(isinstance(transition, dict), "P3-03 transition is missing")
    require(transition.get("post_freeze_stage") == "NEX-P3-04", "P3-03 did not preserve P3-04")


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("schema_version") == "nexora-decision-feed-candidate-details-v1", "schema drift")
    require(contract.get("decision_id") == "NEX-P3-04", "stage ID drift")
    require(contract.get("status") == "candidate", "candidate status drift")
    prerequisite = contract.get("prerequisites")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(
        prerequisite.get("p3_03_accepted_commit_sha") == "7b5d7014655320a750e94245d96847ddf799414f",
        "accepted P3-03 SHA drift",
    )

    api = contract.get("api")
    require(isinstance(api, dict), "API contract missing")
    for key in (
        "owner_scoped",
        "active_generation_only",
        "cursor_bound_to_generation",
        "cursor_bound_to_evidence_sha256",
        "complete_source_reference",
    ):
        require(api.get(key) is True, f"API invariant disabled: {key}")
    require(api.get("staging_generation_visible") is False, "staging generation became visible")
    require(api.get("maximum_page_size") == 100, "page bound drift")
    require(api.get("invalid_projection_action") == "degraded_empty_fail_closed", "fail-closed action drift")

    require(
        set(contract.get("provider_states", [])) == {"ready", "degraded", "disabled_incompatible"},
        "provider state inventory drift",
    )
    require(
        set(contract.get("visible_resource_types", [])) == {"decision_evaluation", "candidate"},
        "visible resource scope drift",
    )
    web = contract.get("web")
    require(isinstance(web, dict) and all(value is True for value in web.values()), "product states weakened")
    security = contract.get("security_boundary")
    require(isinstance(security, dict) and all(value is False for value in security.values()), "security widened")
    scope = contract.get("scope")
    require(isinstance(scope, dict) and all(value is False for value in scope.values()), "future scope added")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition missing")
    require(transition.get("next_allowed_stage") == "NEX-P3-04-FREEZE", "acceptance bypassed")
    require(transition.get("post_freeze_stage") == "NEX-P3-05", "next stage drift")


def validate_implementation() -> None:
    service = SERVICE_PATH.read_text(encoding="utf-8")
    repository = REPOSITORY_PATH.read_text(encoding="utf-8")
    api = API_PATH.read_text(encoding="utf-8")
    web = WEB_PATH.read_text(encoding="utf-8")
    for marker in (
        "VISIBLE_RESOURCE_TYPES",
        "DecisionProjectionRecord.model_validate",
        "cursor is invalid",
        "decision feed snapshot changed",
        "PROJECTION_EVIDENCE_INVALID",
        "PROVIDER_DISABLED_INCOMPATIBLE",
    ):
        require(marker in service, f"service marker missing: {marker}")
    for marker in ("active_snapshot", 'DecisionProjectionState.status == "active"'):
        require(marker in repository, f"owner projection marker missing: {marker}")
    for marker in ('"/v1/decisions"', '"/v1/candidates/{candidate_id}"', "require_session"):
        require(marker in api, f"API marker missing: {marker}")
    for marker in ("providerStates", "source.checksum", "advisoryBoundary", "encodeURIComponent"):
        require(marker in web, f"Web marker missing: {marker}")
    combined = service + api + web
    for forbidden in ("live_order", "exchange_api_key", "wallet_private_key", "fund_transfer"):
        require(forbidden not in combined, f"forbidden capability present: {forbidden}")


def verify() -> None:
    validate_prerequisite()
    validate_contract(load_contract())
    validate_implementation()


def main() -> int:
    verify()
    print("NEX_P3_03_ACCEPTED_SHA=PASS")
    print("NEX_P3_04_DECISION_FEED_CANDIDATE_DETAILS=PASS")
    print("NEX_P3_04_OWNER_SCOPE=PASS")
    print("NEX_P3_04_EXECUTION_CAPABILITY=FORBIDDEN")
    print("NEX_P3_05=BLOCKED_PENDING_P3_04_ACCEPTANCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
