#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-trd-bot-paper-shadow-projection.json"
FREEZE_PATH = ROOT / "artifacts/p2-08/trd-bot-paper-shadow-projection-freeze.json"
P2_07_VERIFIER_PATH = ROOT / "scripts/verify_nav_pnl_performance.py"
P2_07_FREEZE_PATH = ROOT / "artifacts/p2-07/nav-pnl-performance-freeze.json"
P2_07_FREEZE_COMMIT = "c2bda7c3e1ec8407ad3ed50698e87d2c3c5c8ec8"
P2_07_CANDIDATE_COMMIT = "fbdc2999af83352af6379f05438feba4a1723ec5"
P2_07_FREEZE_CHECKSUM = "1b87efa133beec050bec2ffd0e145cb302863f43448396da205c66bc3486fa67"
CONTRACT_CHECKSUM = "c67975344a7741f57d7f6dce494a1f9b8c8f0312a4b14028c8b5621f3c2f8277"
CANDIDATE_SHA = "d53f0e90acaac2de3157e9c535f99070bfb73a9d"
CANDIDATE_TREE_SHA = "b33a761c2d03e38b425d0a8a9614c42ccb388dc7"
CANDIDATE_MESSAGE = "feat(nexora): add TRD Bot Paper Shadow projection"
CANDIDATE_PREDECESSOR = P2_07_FREEZE_COMMIT
CANDIDATE_LINEAGE_CHECKSUM = "3c061b147f901a35b9c37d63fdd8085d556d0840f404c9e699ff20238debf7d4"
WORKFLOW_RUNS_CHECKSUM = "fbf0d97d7c56e362348f726181ad8d4b9a319ff5fa706bae71b002b66dc29a5b"
CHECKS_CHECKSUM = "b3f8c8e03843abd680b858131f790460c40dd6b0481104fe50899352ba7f3dc2"
EXPECTED_WORKFLOW_RUNS = 23
EXPECTED_CHECKS = 75

EXPECTED_ENTITIES = {
    "paper_shadow_portfolio_projection",
    "paper_shadow_position_projection",
    "projection_lineage",
    "projection_issue",
}
EXPECTED_EVENT_TYPES = {
    "simulation.position.opened.v1",
    "simulation.position.updated.v1",
    "simulation.position.closed.v1",
}
EXPECTED_EVENT_SCHEMAS = {
    "simulation-position-opened-v1",
    "simulation-position-updated-v1",
    "simulation-position-closed-v1",
}


class PaperShadowProjectionContractError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PaperShadowProjectionContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.relative_to(ROOT)} must contain an object")
    return payload


def canonical_checksum(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p2_07() -> None:
    spec = importlib.util.spec_from_file_location("verify_nav_pnl_performance", P2_07_VERIFIER_PATH)
    _require(spec is not None and spec.loader is not None, "unable to load P2-07 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contract = module.load_contract()
    freeze = module.load_freeze_record()
    module.validate_frozen_p2_06()
    module.validate_contract(contract)
    module.validate_runtime_markers()
    module.validate_freeze_record(freeze, contract)
    module.validate_freeze_workflow()
    _require(canonical_checksum(freeze) == P2_07_FREEZE_CHECKSUM, "P2-07 Freeze checksum drift")
    _require(freeze.get("candidate_commit_sha") == P2_07_CANDIDATE_COMMIT, "P2-07 candidate drift")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(
        contract.get("schema_version") == "nexora-trd-bot-paper-shadow-projection-contract-v1",
        "invalid projection contract schema",
    )
    _require(contract.get("decision_id") == "NEX-P2-08", "invalid projection decision")
    _require(contract.get("status") == "candidate", "P2-08 must remain a candidate before Freeze")

    prerequisite = contract.get("prerequisite")
    _require(isinstance(prerequisite, dict), "prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-07", "P2-07 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P2-07 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_07_FREEZE_COMMIT, "P2-07 Freeze SHA drift")
    _require(prerequisite.get("accepted_candidate_commit_sha") == P2_07_CANDIDATE_COMMIT, "candidate SHA drift")
    _require(
        prerequisite.get("freeze_record_path") == P2_07_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-07 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_07_FREEZE_CHECKSUM, "Freeze checksum drift")

    scope = contract.get("scope")
    _require(isinstance(scope, dict), "scope must be an object")
    _require(set(scope.get("entities", [])) == EXPECTED_ENTITIES, "projection entity inventory drift")
    _require(set(scope.get("modes", [])) == {"paper", "shadow"}, "projection mode inventory drift")
    for excluded in (
        "live_mode_included",
        "public_api_included",
        "export_included",
        "journal_mutation_included",
        "nav_or_pnl_mutation_included",
    ):
        _require(scope.get(excluded) is False, f"P2-08 cannot enable {excluded}")

    source = contract.get("source_contract")
    _require(isinstance(source, dict), "source contract must be an object")
    _require(source.get("provider") == "trd_bot", "projection provider drift")
    _require(source.get("minimum_provider_version") == "0.3.1", "minimum provider version drift")
    _require(source.get("integration_contract") == "nexora-trd-integration-v1", "integration contract drift")
    _require(
        set(source.get("snapshot_resources", [])) == {"paper_shadow_portfolio", "paper_shadow_position"},
        "snapshot resource inventory drift",
    )
    _require(set(source.get("event_types", [])) == EXPECTED_EVENT_TYPES, "projection event inventory drift")
    _require(
        set(source.get("event_payload_schemas", [])) == EXPECTED_EVENT_SCHEMAS,
        "event payload schema inventory drift",
    )
    _require(source.get("unknown_schema_behavior") == "quarantine_without_projection", "fail-closed drift")
    _require(source.get("direct_database_access") is False, "direct TRD Bot database access enabled")

    invariants = contract.get("projection_invariants")
    _require(isinstance(invariants, dict), "projection invariants must be an object")
    _require(invariants.get("version") == "nexora-trd-bot-paper-shadow-projection-v1", "version drift")
    for required in (
        "owner_scope_required",
        "derived_from_immutable_source_evidence",
        "fully_rebuildable",
        "deterministic_ordering",
        "deterministic_checksum",
        "source_reference_lineage_required",
        "source_payload_sha256_verified",
        "financial_decimal_strings_required",
        "binary_float_forbidden",
        "portfolio_mode_must_match_position_mode",
        "contiguous_position_aggregate_versions_required",
        "gap_preserves_last_verified_state",
        "gap_marks_projection_incomplete",
        "invalid_transition_marks_projection_incomplete",
        "unknown_portfolio_marks_projection_incomplete",
    ):
        _require(invariants.get(required) is True, f"projection invariant requires {required}")
    for forbidden in (
        "projection_is_authoritative_accounting_source",
        "projection_writes_transaction_journal",
        "projection_changes_frozen_nav_or_pnl",
    ):
        _require(invariants.get(forbidden) is False, f"projection invariant forbids {forbidden}")

    durable = contract.get("durable_sync")
    _require(isinstance(durable, dict), "durable sync must be an object")
    for required in (
        "strict_event_payload_validation",
        "unknown_projection_snapshot_is_quarantined",
        "quarantined_snapshot_evidence_preserved",
        "event_checkpoint_and_evidence_atomic",
        "at_least_once_delivery",
    ):
        _require(durable.get(required) is True, f"durable sync requires {required}")
    _require(durable.get("event_job_type") == "trd_bot.event_sync", "event job type drift")
    _require(durable.get("snapshot_job_type") == "trd_bot.snapshot_sync", "snapshot job type drift")
    _require(
        durable.get("invalid_projection_event_reason_code") == "INVALID_PROJECTION_PAYLOAD",
        "projection quarantine reason drift",
    )

    persistence = contract.get("persistence")
    _require(isinstance(persistence, dict), "persistence must be an object")
    _require(persistence.get("read_model_rebuilt_on_demand") is True, "read model rebuild drift")
    _require(persistence.get("new_tables") == [], "P2-08 cannot add mutable projection tables")
    _require(persistence.get("new_migration_required") is False, "unexpected migration requirement")
    _require(persistence.get("mutable_projection_cache") is False, "mutable projection cache enabled")

    runtime = contract.get("runtime_boundary")
    _require(isinstance(runtime, dict), "runtime boundary must be an object")
    _require(runtime.get("repository_composed") is True, "projection repository is not composed")
    _require(runtime.get("new_http_operations") == [], "P2-08 cannot add HTTP operations")
    _require(runtime.get("owner_id_accepted_from_request") is False, "owner override enabled")
    _require(runtime.get("external_provider_smoke_claimed") is False, "external provider smoke claimed")
    _require(runtime.get("incompatible_provider_remains_disabled") is True, "incompatible provider enabled")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security boundary must be an object")
    _require(all(value is False for value in security.values()), "forbidden capability enabled")
    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("next_allowed_stage") == "NEX-P2-08-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P2-09", "post-Freeze stage drift")
    _require(transition.get("freeze_before_portfolio_api_and_export") is True, "Freeze boundary missing")


def validate_runtime_markers() -> None:
    domain = (ROOT / "apps/server/src/nexora/paper_shadow_projection.py").read_text(encoding="utf-8")
    repository = (ROOT / "apps/server/src/nexora/adapters/postgresql/paper_shadow_projection.py").read_text(
        encoding="utf-8"
    )
    sync = (ROOT / "apps/server/src/nexora/trd_bot_sync.py").read_text(encoding="utf-8")
    composition = (ROOT / "apps/server/src/nexora/composition.py").read_text(encoding="utf-8")
    for marker in (
        "class PaperShadowProjectionView",
        "def rebuild_paper_shadow_projection(",
        "AGGREGATE_GAP",
        "financial decimal values must be encoded as strings",
    ):
        _require(marker in domain, f"projection domain marker missing: {marker}")
    for marker in ("class PaperShadowProjectionRepository", "ImmutableSourceEvidence", "SourceReference"):
        _require(marker in repository, f"projection repository marker missing: {marker}")
    for marker in (
        "validate_projection_event",
        "validate_projection_snapshot",
        "INVALID_PROJECTION_PAYLOAD",
        "trd_bot.sync.projection_snapshot.completed.v1",
    ):
        _require(marker in sync, f"durable sync marker missing: {marker}")
    _require("paper_shadow_projection_repository" in composition, "projection repository is not composed")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(
        record.get("schema_version") == "nexora-trd-bot-paper-shadow-projection-freeze-v1",
        "invalid Freeze schema",
    )
    _require(record.get("decision_id") == "NEX-P2-08", "invalid Freeze decision")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "Freeze repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_tree_sha") == CANDIDATE_TREE_SHA, "candidate tree drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "candidate message drift")
    _require(record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR, "candidate predecessor drift")

    lineage = record.get("candidate_lineage")
    _require(isinstance(lineage, list), "candidate lineage must be an array")
    _require(len(lineage) == 1, "candidate lineage must contain the P2-08 implementation commit")
    _require(canonical_checksum(lineage) == CANDIDATE_LINEAGE_CHECKSUM, "candidate lineage drift")
    _require(lineage[0].get("parent_sha") == CANDIDATE_PREDECESSOR, "candidate lineage base drift")
    _require(lineage[-1].get("sha") == CANDIDATE_SHA, "candidate lineage does not end at accepted SHA")

    workflows = record.get("workflow_runs")
    _require(isinstance(workflows, list), "workflow runs must be an array")
    _require(len(workflows) == EXPECTED_WORKFLOW_RUNS, "workflow run inventory drift")
    _require(canonical_checksum(workflows) == WORKFLOW_RUNS_CHECKSUM, "workflow run evidence drift")
    run_ids = {workflow.get("run_id") for workflow in workflows}
    _require(len(run_ids) == EXPECTED_WORKFLOW_RUNS, "workflow run IDs must be unique")
    _require(all(workflow.get("conclusion") == "success" for workflow in workflows), "workflow did not succeed")

    checks = record.get("checks")
    _require(isinstance(checks, list), "checks must be an array")
    _require(len(checks) == EXPECTED_CHECKS, "check inventory drift")
    _require(canonical_checksum(checks) == CHECKS_CHECKSUM, "check evidence drift")
    job_ids = {check.get("job_id") for check in checks}
    _require(len(job_ids) == EXPECTED_CHECKS, "check job IDs must be unique")
    _require(all(check.get("run_id") in run_ids for check in checks), "check references an unknown workflow")
    _require(all(check.get("conclusion") == "success" for check in checks), "check did not succeed")
    _require(
        record.get("check_summary") == {"total": 75, "successful": 75, "failed": 0, "pending": 0},
        "check summary drift",
    )

    contract_evidence = record.get("paper_shadow_projection_contract")
    _require(isinstance(contract_evidence, dict), "projection contract evidence must be an object")
    _require(contract_evidence.get("schema_version") == contract.get("schema_version"), "contract schema drift")
    _require(contract_evidence.get("path") == CONTRACT_PATH.relative_to(ROOT).as_posix(), "contract path drift")
    _require(contract_evidence.get("checksum") == canonical_checksum(contract), "contract evidence drift")
    _require(contract_evidence.get("checksum") == CONTRACT_CHECKSUM, "contract checksum drift")

    prerequisite = record.get("p2_07_prerequisite")
    _require(isinstance(prerequisite, dict), "P2-07 prerequisite evidence must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-07", "P2-07 decision drift")
    _require(prerequisite.get("frozen") is True, "P2-07 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_07_FREEZE_COMMIT, "P2-07 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_07_CANDIDATE_COMMIT,
        "P2-07 candidate drift",
    )
    _require(
        prerequisite.get("freeze_record_path") == P2_07_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-07 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_07_FREEZE_CHECKSUM, "P2-07 checksum drift")

    _require(record.get("recorded_on") == "2026-11-02", "Freeze record date drift")
    _require(record.get("frozen") is True, "P2-08 must be frozen")
    for completed in (
        "paper_shadow_portfolio_projection_complete",
        "paper_shadow_position_projection_complete",
        "deterministic_rebuild_complete",
        "immutable_lineage_complete",
        "gap_and_conflict_detection_complete",
        "unknown_schema_quarantine_complete",
    ):
        _require(record.get(completed) is True, f"Freeze completion missing: {completed}")
    for deferred in (
        "public_api_complete",
        "export_complete",
        "external_provider_smoke_claimed",
        "production_readiness_claimed",
    ):
        _require(record.get(deferred) is False, f"Freeze cannot claim {deferred}")
    for forbidden in (
        "public_internet_deployment",
        "multi_user",
        "exchange_credentials",
        "wallet_private_keys_or_signing",
        "fund_transfer",
        "live_order_capability",
        "autonomous_ai_execution",
        "ml_training_or_inference",
        "financial_advice",
        "tax_advice",
        "direct_trd_bot_database_access",
        "journal_mutation",
        "nav_or_pnl_mutation",
    ):
        _require(record.get(forbidden) is False, f"Freeze enables forbidden capability: {forbidden}")
    _require(record.get("next_allowed_stage") == "NEX-P2-09", "Freeze next stage drift")


def validate_workflow() -> None:
    workflow = (ROOT / ".github/workflows/paper-shadow-projection.yml").read_text(encoding="utf-8")
    for marker in (
        "python3 scripts/verify_nav_pnl_performance.py",
        "python3 scripts/verify_paper_shadow_projection.py",
        "python3 -m unittest discover -s tests -v",
        "uv run ruff format --check",
        "uv run ruff check",
        "uv run mypy",
        'uv run pytest -m "not integration" -q',
        "uv run alembic upgrade head",
        "uv run pytest apps/server/tests/test_postgresql_integration.py -m integration -q",
        "uv run alembic check",
    ):
        _require(marker in workflow, f"P2-08 workflow evidence missing: {marker}")


def main() -> int:
    validate_frozen_p2_07()
    contract = load_contract()
    freeze_record = load_freeze_record()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-08 contract checksum drift")
    validate_runtime_markers()
    validate_freeze_record(freeze_record, contract)
    validate_workflow()
    print("NEX_P2_07_PREREQUISITE=PASS")
    print("NEX_P2_08_PAPER_SHADOW_PROJECTION=PASS")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print(f"p2_07_freeze_checksum={P2_07_FREEZE_CHECKSUM}")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print("NEX_P2_08_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
