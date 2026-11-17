#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-watchlists.json"
DOMAIN_PATH = ROOT / "contracts/nexora-v0.1-decision-review-journal-domain.json"
SERVICE_PATH = ROOT / "apps/server/src/nexora/watchlists.py"
REPOSITORY_PATH = ROOT / "apps/server/src/nexora/adapters/postgresql/watchlists.py"
MODELS_PATH = ROOT / "apps/server/src/nexora/adapters/postgresql/models.py"
MIGRATION_PATH = ROOT / "alembic/versions/20261117_0014_watchlists.py"
API_PATH = ROOT / "apps/server/src/nexora/api.py"
WEB_PATH = ROOT / "apps/web/src/components/watchlist-panel.tsx"


class WatchlistContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WatchlistContractError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def validate_prerequisite() -> None:
    domain = load_json(DOMAIN_PATH)
    require(domain.get("decision_id") == "NEX-P3-01", "P3-01 domain decision drift")
    watchlist = domain.get("watchlist_domain")
    require(isinstance(watchlist, dict), "frozen watchlist domain missing")
    require(watchlist.get("owner_scoped") is True, "owner scope weakened")
    require(watchlist.get("optimistic_concurrency_required") is True, "optimistic concurrency weakened")
    require(watchlist.get("duplicate_item_idempotent") is True, "duplicate registration widened")
    require(watchlist.get("creates_trade_instruction") is False, "trade instruction capability opened")


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("schema_version") == "nexora-watchlists-contract-v1", "schema drift")
    require(contract.get("decision_id") == "NEX-P3-09", "stage ID drift")
    require(contract.get("status") == "candidate", "candidate status drift")
    prerequisite = contract.get("prerequisites")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(
        prerequisite.get("p3_08_accepted_commit_sha") == "0c008cd6d24ec02e28edcb7f94d698341aa2bc8f",
        "accepted P3-08 SHA drift",
    )
    watchlists = contract.get("watchlists")
    require(isinstance(watchlists, dict), "watchlist policy missing")
    require(
        watchlists.get("item_kinds") == ["asset", "market", "strategy", "candidate_source"],
        "watchlist item kind drift",
    )
    for key in (
        "owner_scoped",
        "optimistic_concurrency",
        "idempotency_key_required",
        "exact_payload_replay_is_idempotent",
        "different_payload_replay_is_conflict",
        "duplicate_item_registration_is_idempotent",
        "owner_and_name_unique",
    ):
        require(watchlists.get(key) is True, f"watchlist invariant disabled: {key}")
    preferences = contract.get("monitoring_preferences")
    require(isinstance(preferences, dict), "monitoring preference policy missing")
    require(preferences.get("bounded") is True, "monitoring preferences became unbounded")
    require(
        preferences.get("presentation_orders") == ["newest_first", "oldest_first", "severity_desc"],
        "presentation order drift",
    )
    require(
        preferences.get("minimum_severities") == ["info", "warning", "critical"],
        "minimum severity drift",
    )
    require(preferences.get("notification_delivery_enabled") is False, "notification delivery opened")
    require(
        preferences.get("provider_subscription_management_enabled") is False,
        "provider subscription management opened",
    )
    security = contract.get("security_boundary")
    require(isinstance(security, dict) and all(value is False for value in security.values()), "security widened")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition missing")
    require(transition.get("next_allowed_stage_after_ci_acceptance") == "NEX-P3-10", "next stage drift")
    require(transition.get("separate_freeze_task_required") is False, "separate Freeze task restored")
    require(transition.get("nex_p3_03_gate_opened") is False, "NEX-P3-03 opened prematurely")


def validate_implementation() -> None:
    paths = (SERVICE_PATH, REPOSITORY_PATH, MODELS_PATH, MIGRATION_PATH, API_PATH, WEB_PATH)
    for path in paths:
        require(path.is_file(), f"implementation file missing: {path.name}")
    for path in paths[:-1]:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for marker in (
        "WatchlistRecord",
        "WatchlistItemRecord",
        "WatchlistPreferenceRecord",
        "expected_version",
        "Idempotency-Key",
        '"/v1/watchlists"',
        "provider_subscription_management_enabled",
        "creates_trade_instruction",
    ):
        require(marker in combined, f"watchlist behavior missing: {marker}")
    for forbidden in ("exchange_api_key", "wallet_private_key", "fund_transfer(", "submit_order("):
        require(forbidden not in combined, f"forbidden capability present: {forbidden}")


def verify() -> None:
    validate_prerequisite()
    validate_contract(load_contract())
    validate_implementation()


def main() -> int:
    verify()
    print("NEX_P3_08_ACCEPTED_SHA=PASS")
    print("NEX_P3_09_WATCHLISTS=PASS")
    print("NEX_P3_09_MONITORING_PREFERENCES=BOUNDED")
    print("NEX_P3_09_PROVIDER_SUBSCRIPTION_MANAGEMENT=DEFERRED")
    print("NEX_P3_10=BLOCKED_PENDING_P3_09_CI_ACCEPTANCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
