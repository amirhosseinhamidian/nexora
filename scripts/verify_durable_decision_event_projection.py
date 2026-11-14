#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-durable-decision-event-projection.json"
P3_02_FREEZE_PATH = ROOT / "artifacts/p3-02/trd-bot-v031-integration-contract-freeze.json"
MIGRATION_PATH = ROOT / "alembic/versions/20261112_0011_decision_event_projection.py"
DOMAIN_PATH = ROOT / "apps/server/src/nexora/decision_event_projection.py"
DURABLE_PATH = ROOT / "apps/server/src/nexora/adapters/postgresql/durable.py"
SYNC_PATH = ROOT / "apps/server/src/nexora/trd_bot_sync.py"

EXPECTED_RESOURCES = {
    "market_context",
    "decision_evaluation",
    "candidate",
    "risk_gate",
    "portfolio_intelligence",
    "alert",
    "alert_outcome",
}
EXPECTED_KINDS = {
    "candidate",
    "risk_assessment",
    "portfolio_assessment",
    "monitoring_alert",
}


class DurableDecisionProjectionError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DurableDecisionProjectionError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def validate_prerequisite() -> None:
    freeze = load_json(P3_02_FREEZE_PATH)
    require(freeze.get("decision_id") == "NEX-P3-02", "P3-02 Freeze decision drift")
    require(freeze.get("frozen") is True, "P3-02 is not frozen")
    transition = freeze.get("transition")
    require(isinstance(transition, dict), "P3-02 transition is missing")
    require(transition.get("nexora_next_stage") == "NEX-P3-03", "P3-02 did not preserve P3-03")
    require(
        transition.get("nexora_next_stage_blocked_until") == "compatible_provider_and_real_smoke",
        "P3-02 provider smoke gate drift",
    )


def validate_contract(contract: dict[str, Any]) -> None:
    require(
        contract.get("schema_version") == "nexora-durable-decision-event-projection-v1",
        "contract schema drift",
    )
    require(contract.get("decision_id") == "NEX-P3-03", "stage ID drift")
    require(contract.get("status") == "candidate", "candidate status drift")
    prerequisite = contract.get("prerequisites")
    require(isinstance(prerequisite, dict), "prerequisites must be an object")
    require(prerequisite.get("trd_bot_release") == "0.3.1", "provider release drift")
    require(
        prerequisite.get("trd_bot_release_commit_sha") == "3097276ed77cd212101797654452456b7fbc61de",
        "provider commit drift",
    )
    require(
        str(prerequisite.get("real_local_provider_smoke_digest", "")).startswith("sha256:"),
        "real provider smoke evidence missing",
    )

    persistence = contract.get("persistence")
    require(isinstance(persistence, dict), "persistence must be an object")
    require(persistence.get("migration_revision") == "20261112_0011", "migration revision drift")
    for key in (
        "owner_scoped",
        "generation_staging",
        "checkpoint_and_projection_share_job_transaction",
        "projection_checksum_required",
        "source_evidence_immutable",
        "quarantine_auditable",
    ):
        require(persistence.get(key) is True, f"persistence invariant disabled: {key}")
    require(
        persistence.get("partial_generation_publish_allowed") is False,
        "partial projection publication enabled",
    )

    projection = contract.get("projection")
    require(isinstance(projection, dict), "projection must be an object")
    require(set(projection.get("resource_types", [])) == EXPECTED_RESOURCES, "resource inventory drift")
    require(set(projection.get("decision_kinds", [])) == EXPECTED_KINDS, "decision kind drift")
    require(projection.get("unknown_schema_action") == "quarantine_and_reject_generation", "schema gate weakened")
    require(projection.get("duplicate_event_action") == "idempotent_noop", "replay semantics drift")
    require(
        projection.get("aggregate_gap_action") == "quarantine_pause_and_full_resync",
        "gap recovery weakened",
    )

    resync = contract.get("full_resync")
    require(isinstance(resync, dict), "full_resync must be an object")
    for key in (
        "all_projected_resources_required",
        "activation_requires_zero_quarantine",
        "event_resume_enqueued_only_after_activation",
        "previous_active_generation_preserved_on_rejection",
    ):
        require(resync.get(key) is True, f"resync invariant disabled: {key}")
    require(resync.get("staging_generation_visible_to_owner") is False, "staging data became visible")

    security = contract.get("security_boundary")
    require(isinstance(security, dict), "security boundary must be an object")
    require(all(value is False for value in security.values()), "forbidden security capability enabled")
    scope = contract.get("scope")
    require(isinstance(scope, dict) and all(value is False for value in scope.values()), "scope widened")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition must be an object")
    require(transition.get("next_allowed_stage") == "NEX-P3-03-FREEZE", "next stage bypasses acceptance")
    require(transition.get("post_freeze_stage") == "NEX-P3-04", "post-acceptance stage drift")


def validate_implementation() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    domain = DOMAIN_PATH.read_text(encoding="utf-8")
    durable = DURABLE_PATH.read_text(encoding="utf-8")
    sync = SYNC_PATH.read_text(encoding="utf-8")
    for marker in (
        'revision: str = "20261112_0011"',
        'down_revision: str | None = "20261101_0010"',
        '"decision_projection_states"',
        "uq_decision_projection_states_owner_active",
    ):
        require(marker in migration, f"migration marker missing: {marker}")
    for marker in (
        "SNAPSHOT_SCHEMA_ALLOWLIST",
        "EVENT_SCHEMA_ALLOWLIST",
        "source_reference_checksum",
        "project_snapshot",
        "project_event",
    ):
        require(marker in domain, f"domain marker missing: {marker}")
    for marker in (
        "DecisionProjectionMutation",
        "_mutate_decision_projection",
        "enqueue_after_projection_activation",
        "PROJECTED_RESOURCES",
    ):
        require(marker in durable, f"atomic persistence marker missing: {marker}")
    for marker in (
        "INITIAL_SNAPSHOT_REQUIRED",
        "AGGREGATE_VERSION_GAP",
        "INVALID_OR_UNSUPPORTED_SNAPSHOT",
        "enqueue_after_projection_activation",
    ):
        require(marker in sync, f"sync recovery marker missing: {marker}")
    combined = domain + durable + sync
    for forbidden in ("live_order", "exchange_api_key", "wallet_private_key", "fund_transfer"):
        require(forbidden not in combined, f"forbidden capability present: {forbidden}")


def verify() -> None:
    validate_prerequisite()
    validate_contract(load_contract())
    validate_implementation()


def main() -> int:
    verify()
    print("NEX_P3_02_FREEZE=PASS")
    print("NEX_P3_03_DURABLE_DECISION_EVENT_PROJECTION=PASS")
    print("NEX_P3_03_PARTIAL_PUBLICATION=FORBIDDEN")
    print("NEX_P3_04=BLOCKED_PENDING_P3_03_ACCEPTANCE")
    print("NEX_V0_1_SERVER_DEPLOYMENT_GATE=PRESERVED_DEFERRED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
