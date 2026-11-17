#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-alert-inbox.json"
DOMAIN_PATH = ROOT / "contracts/nexora-v0.1-decision-review-journal-domain.json"
SERVICE_PATH = ROOT / "apps/server/src/nexora/alert_inbox.py"
REPOSITORY_PATH = ROOT / "apps/server/src/nexora/adapters/postgresql/alert_inbox.py"
MODELS_PATH = ROOT / "apps/server/src/nexora/adapters/postgresql/models.py"
MIGRATION_PATH = ROOT / "alembic/versions/20261117_0013_alert_inbox.py"
API_PATH = ROOT / "apps/server/src/nexora/api.py"
WEB_PATH = ROOT / "apps/web/src/components/alert-inbox.tsx"


class AlertInboxContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AlertInboxContractError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def validate_prerequisite() -> None:
    domain = load_json(DOMAIN_PATH)
    require(domain.get("decision_id") == "NEX-P3-01", "P3-01 domain decision drift")
    alert = domain.get("alert_domain")
    require(isinstance(alert, dict), "frozen alert domain missing")
    require(alert.get("source_alert_immutable") is True, "source alert immutability weakened")
    require(alert.get("state_history_append_only") is True, "alert history mutability widened")
    require(alert.get("notification_delivery_deferred") is True, "notification delivery opened")


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("schema_version") == "nexora-alert-inbox-contract-v1", "schema drift")
    require(contract.get("decision_id") == "NEX-P3-08", "stage ID drift")
    require(contract.get("status") == "candidate", "candidate status drift")
    prerequisite = contract.get("prerequisites")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(
        prerequisite.get("p3_07_accepted_commit_sha") == "ec8922357e207f318df6898c2ddb64bd8bfb84a4",
        "accepted P3-07 SHA drift",
    )
    source = contract.get("source_alerts")
    require(isinstance(source, dict) and all(source.values()), "source alert invariant disabled")
    owner = contract.get("owner_state")
    require(isinstance(owner, dict), "owner state policy missing")
    require(
        owner.get("local_states") == ["open", "acknowledged", "snoozed", "resolved", "expired"],
        "alert state set drift",
    )
    require(owner.get("owner_actions") == ["acknowledge", "snooze"], "owner action set drift")
    for key in (
        "owner_scoped",
        "history_append_only",
        "optimistic_concurrency",
        "idempotency_key_required",
        "exact_payload_replay_is_idempotent",
        "different_payload_replay_is_conflict",
        "snooze_until_required",
        "expired_snooze_reopens_for_presentation",
        "source_terminal_state_precedence",
    ):
        require(owner.get(key) is True, f"owner state invariant disabled: {key}")
    delivery = contract.get("notification_delivery")
    require(
        isinstance(delivery, dict) and delivery.get("enabled") is False and delivery.get("deferred") is True,
        "notification delivery boundary widened",
    )
    security = contract.get("security_boundary")
    require(isinstance(security, dict) and all(value is False for value in security.values()), "security widened")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition missing")
    require(transition.get("next_allowed_stage_after_ci_acceptance") == "NEX-P3-09", "next stage drift")
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
        "OwnerAlertStateRecord",
        "AlertStateHistoryRecord",
        "expected_version",
        "snooze_until",
        "source_evidence_checksum",
        "Idempotency-Key",
        '"/v1/alerts"',
        '"/v1/alerts/{alert_id}/state-transitions"',
        "notification_delivery_enabled",
    ):
        require(marker in combined, f"alert behavior missing: {marker}")
    for forbidden in ("exchange_api_key", "wallet_private_key", "fund_transfer(", "submit_order("):
        require(forbidden not in combined, f"forbidden capability present: {forbidden}")


def verify() -> None:
    validate_prerequisite()
    validate_contract(load_contract())
    validate_implementation()


def main() -> int:
    verify()
    print("NEX_P3_07_ACCEPTED_SHA=PASS")
    print("NEX_P3_08_ALERT_INBOX=PASS")
    print("NEX_P3_08_SOURCE_ALERT_IMMUTABILITY=PASS")
    print("NEX_P3_08_NOTIFICATION_DELIVERY=DEFERRED")
    print("NEX_P3_09=BLOCKED_PENDING_P3_08_CI_ACCEPTANCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
