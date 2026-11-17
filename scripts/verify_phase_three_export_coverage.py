#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-three-export-coverage.json"
DOMAIN_PATH = ROOT / "contracts/nexora-v0.1-decision-review-journal-domain.json"
SOURCE_PATH = ROOT / "apps/server/src/nexora/adapters/postgresql/portfolio_export.py"
EXPORT_PATH = ROOT / "apps/server/src/nexora/portfolio_export.py"
API_PATH = ROOT / "apps/server/src/nexora/api.py"
WORKFLOW_PATH = ROOT / ".github/workflows/phase-three-export-coverage.yml"

EXPECTED_DOMAINS = {
    "decision_records",
    "source_references",
    "human_reviews",
    "portfolio_impacts",
    "alert_state_history",
    "watchlists",
    "outcome_journal",
    "lineage",
    "uncertainty",
}
EXPECTED_DATASETS = {
    "decision_records",
    "decision_projection_states",
    "source_references",
    "human_reviews",
    "decision_review_states",
    "decision_review_deliveries",
    "portfolio_impacts",
    "owner_alert_states",
    "alert_state_history",
    "watchlists",
    "watchlist_items",
    "watchlist_preferences",
    "watchlist_operations",
    "outcome_journal",
}
EXPECTED_AI_SAFE_EXCLUSIONS = {
    "credentials",
    "tokens",
    "session_identifiers",
    "recovery_material",
    "private_keys",
    "raw_security_context",
    "provider_raw_payloads",
    "owner_free_text",
    "provider_delivery_identifiers",
    "idempotency_material",
}


class PhaseThreeExportCoverageError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseThreeExportCoverageError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def validate_prerequisite() -> None:
    domain = load_json(DOMAIN_PATH)
    export = domain.get("export_policy")
    require(isinstance(export, dict), "frozen export policy missing")
    require(set(export.get("profiles", [])) == {"private_complete", "ai_safe"}, "export profile drift")
    require(set(export.get("required_domains", [])) == EXPECTED_DOMAINS, "frozen export domain drift")
    require(export.get("owner_scope_required") is True, "owner scope weakened")
    require(export.get("checksums_required") is True, "checksum boundary weakened")
    require(export.get("public_download") is False, "public export opened")


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("schema_version") == "nexora-phase-three-export-coverage-v1", "schema drift")
    require(contract.get("decision_id") == "NEX-P3-11", "stage ID drift")
    require(contract.get("status") == "candidate", "candidate status drift")
    prerequisite = contract.get("prerequisites")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(
        prerequisite.get("p3_10_accepted_commit_sha") == "7e6d646c789849561654ea060291eeaa26a71702",
        "accepted P3-10 SHA drift",
    )
    require(set(contract.get("profiles", [])) == {"private_complete", "ai_safe"}, "profile drift")
    require(set(contract.get("required_domains", [])) == EXPECTED_DOMAINS, "domain coverage drift")
    require(set(contract.get("required_datasets", [])) == EXPECTED_DATASETS, "dataset coverage drift")
    snapshot = contract.get("snapshot")
    require(isinstance(snapshot, dict), "snapshot policy missing")
    for key in (
        "owner_scoped",
        "repeatable_read",
        "schema_versioned",
        "generated_at_required",
        "complete_export_required",
        "bounded_record_count",
        "deterministic_ordering",
    ):
        require(snapshot.get(key) is True, f"snapshot invariant disabled: {key}")
    require(snapshot.get("partial_export_allowed") is False, "partial export enabled")
    checksums = contract.get("checksums")
    require(isinstance(checksums, dict) and all(checksums.values()), "checksum coverage weakened")
    ai_safe = contract.get("ai_safe")
    require(isinstance(ai_safe, dict), "AI-safe policy missing")
    require(set(ai_safe.get("excluded_categories", [])) == EXPECTED_AI_SAFE_EXCLUSIONS, "AI-safe exclusions drift")
    for key in (
        "required_domains_remain_covered",
        "lineage_preserved",
        "uncertainty_preserved",
        "outcome_content_excluded",
        "review_note_excluded",
    ):
        require(ai_safe.get(key) is True, f"AI-safe invariant disabled: {key}")
    require(ai_safe.get("public_download") is False, "AI-safe public download enabled")
    persistence = contract.get("persistence")
    require(isinstance(persistence, dict), "persistence policy missing")
    require(persistence.get("existing_export_artifact_type") == "portfolio-export", "artifact type drift")
    require(persistence.get("existing_authenticated_create_path") == "/v1/portfolio-exports", "API path drift")
    require(persistence.get("new_tables") == [], "unexpected table added")
    for key in ("new_migration_required", "new_public_route", "public_bucket"):
        require(persistence.get(key) is False, f"persistence boundary widened: {key}")
    security = contract.get("security_boundary")
    require(isinstance(security, dict) and not any(security.values()), "security boundary widened")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition missing")
    require(transition.get("next_allowed_stage_after_ci_acceptance") == "NEX-P3-12", "next stage drift")
    require(transition.get("production_readiness_claimed") is False, "production readiness claimed")


def validate_implementation() -> None:
    for path in (SOURCE_PATH, EXPORT_PATH, API_PATH):
        require(path.is_file(), f"implementation missing: {path.name}")
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    source = SOURCE_PATH.read_text(encoding="utf-8")
    export = EXPORT_PATH.read_text(encoding="utf-8")
    api = API_PATH.read_text(encoding="utf-8")
    for marker in (
        "PHASE_THREE_REQUIRED_DATASETS",
        '"decision_records"',
        '"human_reviews"',
        '"portfolio_impacts"',
        '"alert_state_history"',
        '"watchlists"',
        '"outcome_journal"',
        '"phase_three_dataset_sha256"',
        'execution_options={"isolation_level": "REPEATABLE READ"}',
    ):
        require(marker in source, f"Phase 3 export marker missing: {marker}")
    for forbidden in ("BrowserSession", "RecoveryCode", "WebAuthnCredential", "SecurityAuditEvent"):
        require(forbidden not in source, f"security model entered export source: {forbidden}")
    require('public_download": False' in export, "public download boundary missing")
    require(
        "missing_datasets = PHASE_THREE_REQUIRED_DATASETS.difference" in export,
        "complete Phase 3 dataset guard missing",
    )
    require("PHASE_THREE_SOURCE_CHECKSUM_FIELDS" in export, "source checksum guard missing")
    require("Phase 3 dataset checksum mismatch" in export, "dataset checksum verification missing")
    require('"/v1/portfolio-exports"' in api, "authenticated export route missing")


def validate_workflow() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    for marker in (
        "python3 scripts/verify_outcome_journal.py",
        "python3 scripts/verify_phase_three_export_coverage.py",
        "python3 -m unittest discover -s tests -v",
        "uv run ruff format --check",
        "uv run ruff check",
        "uv run mypy",
        'uv run pytest -m "not integration" -q',
        "uv run alembic upgrade head",
        "portfolio_export or current_migration_head",
        "uv run alembic check",
    ):
        require(marker in workflow, f"P3-11 workflow marker missing: {marker}")


def verify() -> None:
    validate_prerequisite()
    validate_contract(load_contract())
    validate_implementation()
    validate_workflow()


def main() -> int:
    verify()
    print("NEX_P3_10_ACCEPTED_SHA=PASS")
    print("NEX_P3_11_PHASE_THREE_EXPORT_COVERAGE=COMPLETE")
    print("NEX_P3_11_AI_SAFE_LINEAGE_AND_UNCERTAINTY=PRESERVED")
    print("NEX_P3_11_PUBLIC_DOWNLOAD=FORBIDDEN")
    print("NEX_P3_12=BLOCKED_PENDING_P3_11_CI_ACCEPTANCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
