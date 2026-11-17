#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-outcome-journal.json"
DOMAIN_PATH = ROOT / "contracts/nexora-v0.1-decision-review-journal-domain.json"
SERVICE_PATH = ROOT / "apps/server/src/nexora/outcome_journal.py"
REPOSITORY_PATH = ROOT / "apps/server/src/nexora/adapters/postgresql/outcome_journal.py"
MODELS_PATH = ROOT / "apps/server/src/nexora/adapters/postgresql/models.py"
MIGRATION_PATH = ROOT / "alembic/versions/20261117_0015_outcome_journal.py"
API_PATH = ROOT / "apps/server/src/nexora/api.py"
WEB_PATH = ROOT / "apps/web/src/components/outcome-journal-panel.tsx"


class OutcomeJournalContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OutcomeJournalContractError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def validate_prerequisite() -> None:
    domain = load_json(DOMAIN_PATH)
    require(domain.get("decision_id") == "NEX-P3-01", "P3-01 domain decision drift")
    journal = domain.get("outcome_journal")
    require(isinstance(journal, dict), "frozen outcome journal domain missing")
    require(journal.get("append_only") is True, "append-only boundary weakened")
    require(journal.get("owner_scoped") is True, "owner scope weakened")
    require(journal.get("decision_reference_required") is True, "decision reference weakened")
    require(
        journal.get("source_lineage_required_for_observed_outcome") is True,
        "observed outcome lineage weakened",
    )
    require(journal.get("mutation_after_recording") == "forbidden", "journal mutation opened")
    require(journal.get("ai_generated_entry_allowed") is False, "AI-authored journal opened")


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("schema_version") == "nexora-outcome-journal-contract-v1", "schema drift")
    require(contract.get("decision_id") == "NEX-P3-10", "stage ID drift")
    require(contract.get("status") == "candidate", "candidate status drift")
    prerequisite = contract.get("prerequisites")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(
        prerequisite.get("p3_09_accepted_commit_sha") == "7a06093b5ce81a60353797e61d8aadcbd40b40e0",
        "accepted P3-09 SHA drift",
    )
    journal = contract.get("journal")
    require(isinstance(journal, dict), "journal policy missing")
    require(
        journal.get("entry_kinds")
        == [
            "owner_note",
            "review_rationale",
            "observed_outcome",
            "expectation_comparison",
            "lesson",
            "correction",
        ],
        "entry kind drift",
    )
    require(
        journal.get("uncertainty_levels") == ["low", "medium", "high", "unknown"],
        "uncertainty level drift",
    )
    for key in (
        "owner_scoped",
        "append_only",
        "decision_reference_required",
        "occurred_at_required",
        "recorded_at_required",
        "idempotency_key_required",
        "exact_payload_replay_is_idempotent",
        "different_payload_replay_is_conflict",
        "correction_requires_superseded_entry",
        "single_direct_correction_per_entry",
    ):
        require(journal.get(key) is True, f"journal invariant disabled: {key}")
    require(journal.get("mutation_after_recording") is False, "journal update opened")
    require(journal.get("deletion") is False, "journal deletion opened")
    lineage = contract.get("lineage")
    require(isinstance(lineage, dict), "lineage policy missing")
    require(lineage.get("decision_source_snapshot_required") is True, "decision source link weakened")
    require(
        lineage.get("source_kinds")
        == ["provider_evidence", "portfolio_snapshot", "manual_observation", "external_record"],
        "source kind drift",
    )
    require(lineage.get("decision_evidence_generation_required") is True, "generation link weakened")
    require(lineage.get("decision_evidence_checksum_required") is True, "decision checksum weakened")
    require(
        lineage.get("observed_outcome_source_lineage_required") is True,
        "observed outcome lineage weakened",
    )
    require(lineage.get("human_note_rewritten_by_provider_sync") is False, "provider rewrite opened")
    api = contract.get("api")
    require(isinstance(api, dict), "API policy missing")
    require(api.get("update_endpoint") is False, "journal update endpoint opened")
    require(api.get("delete_endpoint") is False, "journal delete endpoint opened")
    security = contract.get("security_boundary")
    require(isinstance(security, dict) and all(value is False for value in security.values()), "security widened")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition missing")
    require(transition.get("next_allowed_stage_after_ci_acceptance") == "NEX-P3-11", "next stage drift")
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
        "OutcomeJournalEntryRecord",
        "supersedes_entry_id",
        "decision_evidence_checksum",
        "source_lineage",
        "Idempotency-Key",
        '"/v1/decisions/{decision_id}/journal"',
        "ai_generated",
        "provider_rewritable",
    ):
        require(marker in combined, f"outcome journal behavior missing: {marker}")
    for forbidden in ("exchange_api_key", "wallet_private_key", "fund_transfer(", "submit_order("):
        require(forbidden not in combined, f"forbidden capability present: {forbidden}")


def verify() -> None:
    validate_prerequisite()
    validate_contract(load_contract())
    validate_implementation()


def main() -> int:
    verify()
    print("NEX_P3_09_ACCEPTED_SHA=PASS")
    print("NEX_P3_10_OUTCOME_JOURNAL=APPEND_ONLY")
    print("NEX_P3_10_OBSERVED_OUTCOME_LINEAGE=REQUIRED")
    print("NEX_P3_10_AI_GENERATED_ENTRIES=FORBIDDEN")
    print("NEX_P3_11=BLOCKED_PENDING_P3_10_CI_ACCEPTANCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
