#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-import-reconciliation.json"
FREEZE_PATH = ROOT / "artifacts/p2-04/import-reconciliation-freeze.json"
P2_03_FREEZE_PATH = ROOT / "artifacts/p2-03/transaction-journal-freeze.json"
P2_03_VERIFIER_PATH = ROOT / "scripts/verify_transaction_journal.py"
P2_03_FREEZE_COMMIT = "35572e1fba3c023e512ef2e101749fc77df29e41"
P2_03_CANDIDATE_COMMIT = "cf3ddd90eed968a4f672e78866338d97e68e3e25"
P2_03_FREEZE_CHECKSUM = "5d1614ec2f48ea3c3ad2718f5bafbe466feaf6d924404a18122c482a0ccbe9d0"
CONTRACT_CHECKSUM = "63f04dbeb557eb47fbae96ae76aaef69417c4d6914df793b914f138ab9fad1c9"
CANDIDATE_SHA = "8e1f59f4084f902b4917d91f6ee9593217dbca1e"
CANDIDATE_TREE_SHA = "a2ac3141f8657be9ddd0a2cb531e526952c2c19a"
CANDIDATE_MESSAGE = "feat(nexora): add import and reconciliation runtime"
CANDIDATE_PREDECESSOR = "35572e1fba3c023e512ef2e101749fc77df29e41"
CANDIDATE_LINEAGE_CHECKSUM = "4527134d408a5cec94a8787690a269efa772ef9b13d71e1b3e778c55c268b60a"
WORKFLOW_RUNS_CHECKSUM = "320700398ac961103662e671fe0d77ff82549afd8a31bfab24af1330e653dac5"
CHECKS_CHECKSUM = "e746b1342519a81940bb59964717493a61f66d57fc7b6bb4b527b399a6ed0abd"
EXPECTED_WORKFLOW_RUNS = 19
EXPECTED_CHECKS = 63

EXPECTED_OPERATIONS = {
    "POST /v1/imports/dry-runs",
    "GET /v1/imports",
    "GET /v1/imports/{import_batch_id}",
    "POST /v1/imports/{import_batch_id}/reviews",
    "POST /v1/imports/{import_batch_id}/publication",
    "GET /v1/reconciliation-cases",
    "POST /v1/reconciliation-cases/{reconciliation_case_id}/decisions",
}
FORBIDDEN_CAPABILITIES = {
    "raw_exchange_credentials",
    "wallet_private_keys",
    "wallet_seed_phrases",
    "wallet_signing",
    "fund_transfer",
    "live_orders",
    "direct_trd_bot_database_access",
    "multi_user",
    "saas",
    "autonomous_ai_execution",
    "ml_training_or_inference",
    "financial_advice",
}


class ImportReconciliationContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ImportReconciliationContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p2_03() -> None:
    spec = importlib.util.spec_from_file_location("verify_transaction_journal", P2_03_VERIFIER_PATH)
    _require(spec is not None and spec.loader is not None, "unable to load P2-03 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_p2_02()
    contract = module.load_contract()
    freeze = module.load_freeze_record()
    module.validate_contract(contract)
    module.validate_runtime_markers()
    module.validate_freeze_record(freeze, contract)
    module.validate_freeze_workflow()
    _require(canonical_checksum(freeze) == P2_03_FREEZE_CHECKSUM, "P2-03 Freeze record checksum drift")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-import-reconciliation-contract-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P2-04", "invalid decision")
    _require(contract.get("decision_date") == "2026-10-31", "invalid decision date")
    _require(contract.get("status") == "candidate", "P2-04 must remain candidate before Freeze")
    prerequisite = contract.get("prerequisite")
    _require(isinstance(prerequisite, dict), "prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-03", "P2-03 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P2-03 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_03_FREEZE_COMMIT, "P2-03 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_03_CANDIDATE_COMMIT,
        "P2-03 candidate drift",
    )
    _require(
        prerequisite.get("freeze_record_path") == P2_03_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-03 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_03_FREEZE_CHECKSUM, "P2-03 checksum drift")

    scope = contract.get("scope")
    _require(isinstance(scope, dict), "scope must be an object")
    _require(set(scope.get("source_formats", [])) == {"csv", "nexora_json"}, "source format drift")
    _require(scope.get("maximum_content_bytes") == 1_048_576, "content limit drift")
    _require(scope.get("maximum_rows_per_batch") == 5_000, "row limit drift")
    for deferred in (
        "trd_bot_projection_included",
        "holdings_projection_included",
        "cost_basis_included",
        "valuation_included",
    ):
        _require(scope.get(deferred) is False, f"P2-04 cannot include {deferred}")

    invariants = contract.get("import_invariants")
    _require(isinstance(invariants, dict), "import_invariants must be an object")
    for invariant in (
        "dry_run_required",
        "deterministic_normalization",
        "content_sha256_required",
        "row_fingerprint_sha256_required",
        "idempotent_reimport",
        "duplicate_within_batch_detected",
        "duplicate_across_batches_detected",
        "unknown_fields_quarantined",
        "unknown_schema_rejected",
        "exact_decimal_strings_required",
        "owner_scope_required",
        "partial_publish_forbidden",
        "quarantined_batch_publish_forbidden",
        "owner_review_before_publish",
        "publication_transactional",
    ):
        _require(invariants.get(invariant) is True, f"import invariant requires {invariant}")

    reconciliation = contract.get("reconciliation_policy")
    _require(isinstance(reconciliation, dict), "reconciliation_policy must be an object")
    _require(
        set(reconciliation.get("states", []))
        == {"open", "matched", "accepted_difference", "resolved", "ignored_with_reason"},
        "reconciliation state drift",
    )
    for required in (
        "append_only_decision_evidence",
        "owner_reason_required_for_decisions",
        "optimistic_concurrency",
        "journal_correction_requires_existing_reversal_or_supersession_flow",
    ):
        _require(reconciliation.get(required) is True, f"reconciliation policy requires {required}")
    for forbidden in ("automatic_destructive_fix", "automatic_journal_correction"):
        _require(reconciliation.get(forbidden) is False, f"reconciliation policy forbids {forbidden}")

    persistence = contract.get("persistence")
    _require(isinstance(persistence, dict), "persistence must be an object")
    _require(persistence.get("migration_revision") == "20261031_0008", "migration revision drift")
    _require(len(persistence.get("tables", [])) == 4, "persistence table inventory drift")
    for required in (
        "composite_owner_foreign_keys",
        "reconciliation_decisions_immutable",
        "upgrade_downgrade_rebuild_drift_cycle_required",
    ):
        _require(persistence.get(required) is True, f"persistence requires {required}")

    runtime = contract.get("runtime_api")
    _require(isinstance(runtime, dict), "runtime_api must be an object")
    _require(runtime.get("authentication") == "opaque_owner_session", "authentication drift")
    _require(runtime.get("owner_id_accepted_from_request") is False, "owner override is forbidden")
    _require(runtime.get("csrf_for_mutations") is True, "CSRF protection is required")
    _require(runtime.get("recent_reauthentication_for_publication_and_decisions") is True, "reauth drift")
    _require(set(runtime.get("operations", [])) == EXPECTED_OPERATIONS, "API operation inventory drift")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security_boundary must be an object")
    _require(set(security) == FORBIDDEN_CAPABILITIES, "security capability inventory drift")
    for capability in FORBIDDEN_CAPABILITIES:
        _require(security.get(capability) is False, f"forbidden capability enabled: {capability}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_candidate") is True, "P2-04 is not ready for candidate")
    _require(transition.get("next_allowed_stage") == "NEX-P2-04-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P2-05", "post-Freeze stage drift")
    _require(transition.get("freeze_before_holdings_projection") is True, "P2-05 must remain blocked")


def validate_runtime_markers() -> None:
    paths = {
        "domain": ROOT / "apps/server/src/nexora/import_reconciliation.py",
        "repository": ROOT / "apps/server/src/nexora/adapters/postgresql/import_reconciliation.py",
        "models": ROOT / "apps/server/src/nexora/adapters/postgresql/models.py",
        "migration": ROOT / "alembic/versions/20261031_0008_import_reconciliation_runtime.py",
        "api": ROOT / "apps/server/src/nexora/api.py",
    }
    content = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    for marker in ("def normalize_import", "DUPLICATE_WITHIN_BATCH", "MAX_IMPORT_ROWS = 5_000"):
        _require(marker in content["domain"], f"missing import domain marker: {marker}")
    for marker in ("class ImportReconciliationRepository", "def publish_batch", ".with_for_update()"):
        _require(marker in content["repository"], f"missing import repository marker: {marker}")
    for marker in (
        "class ImportBatchRecord",
        "class ImportRowRecord",
        "class ReconciliationCaseRecord",
        "class ReconciliationDecisionRecord",
    ):
        _require(marker in content["models"], f"missing persistence marker: {marker}")
    _require('revision: str = "20261031_0008"' in content["migration"], "migration marker missing")
    _require("trg_reconciliation_decisions_immutable" in content["migration"], "evidence trigger missing")
    for operation in EXPECTED_OPERATIONS:
        path = operation.split(" ", 1)[1]
        _require(f'"{path}"' in content["api"], f"missing API operation: {operation}")
    openapi = _json(ROOT / "contracts/runtime/v1/openapi.json")
    operations = {
        f"{method.upper()} {path}"
        for path, item in openapi["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    _require(operations >= EXPECTED_OPERATIONS, "P2-04 OpenAPI operation inventory drift")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-import-reconciliation-freeze-v1", "invalid Freeze schema")
    _require(record.get("decision_id") == "NEX-P2-04", "invalid Freeze decision")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "Freeze repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_tree_sha") == CANDIDATE_TREE_SHA, "candidate tree drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "candidate message drift")
    _require(record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR, "candidate predecessor drift")

    lineage = record.get("candidate_lineage")
    _require(isinstance(lineage, list), "candidate lineage must be an array")
    _require(len(lineage) == 1, "candidate lineage must contain the P2-04 candidate")
    _require(canonical_checksum(lineage) == CANDIDATE_LINEAGE_CHECKSUM, "candidate lineage drift")
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
        record.get("check_summary") == {"total": 63, "successful": 63, "failed": 0, "pending": 0},
        "check summary drift",
    )

    contract_evidence = record.get("import_reconciliation_contract")
    _require(isinstance(contract_evidence, dict), "import reconciliation evidence must be an object")
    _require(contract_evidence.get("schema_version") == contract.get("schema_version"), "contract schema drift")
    _require(contract_evidence.get("path") == CONTRACT_PATH.relative_to(ROOT).as_posix(), "contract path drift")
    _require(contract_evidence.get("checksum") == canonical_checksum(contract), "contract evidence drift")
    _require(contract_evidence.get("checksum") == CONTRACT_CHECKSUM, "contract checksum drift")

    prerequisite = record.get("p2_03_prerequisite")
    _require(isinstance(prerequisite, dict), "P2-03 prerequisite evidence must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-03", "P2-03 decision drift")
    _require(prerequisite.get("frozen") is True, "P2-03 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_03_FREEZE_COMMIT, "P2-03 Freeze commit drift")
    _require(prerequisite.get("accepted_candidate_commit_sha") == P2_03_CANDIDATE_COMMIT, "P2-03 candidate drift")
    _require(
        prerequisite.get("freeze_record_path") == P2_03_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-03 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_03_FREEZE_CHECKSUM, "P2-03 checksum drift")

    _require(record.get("recorded_on") == "2026-10-31", "Freeze record date drift")
    _require(record.get("frozen") is True, "P2-04 must be frozen")
    _require(record.get("import_reconciliation_complete") is True, "import completion evidence missing")
    for deferred in (
        "holdings_projection_complete",
        "lots_cost_basis_complete",
        "valuation_complete",
        "pnl_complete",
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
        "direct_trd_bot_database_access",
    ):
        _require(record.get(forbidden) is False, f"Freeze enables forbidden capability: {forbidden}")
    _require(record.get("next_allowed_stage") == "NEX-P2-05", "Freeze next stage drift")


def validate_freeze_workflow() -> None:
    workflow = (ROOT / ".github/workflows/import-reconciliation.yml").read_text(encoding="utf-8")
    for marker in (
        "Verify frozen P2-03 prerequisite",
        "Verify P2-04 import and reconciliation contract",
        "python3 -m unittest discover -s tests -v",
        "uv run ruff format --check",
        "uv run ruff check",
        "uv run mypy",
        'uv run pytest -m "not integration" -q',
        "uv run alembic upgrade head",
        "uv run pytest apps/server/tests/test_postgresql_integration.py -m integration -q",
        "uv run alembic downgrade base",
        "uv run alembic check",
    ):
        _require(marker in workflow, f"P2-04 workflow evidence missing: {marker}")


def main() -> int:
    validate_frozen_p2_03()
    contract = load_contract()
    freeze_record = load_freeze_record()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-04 contract checksum drift")
    validate_runtime_markers()
    validate_freeze_record(freeze_record, contract)
    validate_freeze_workflow()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P2_03_PREREQUISITE=PASS")
    print("NEX_P2_04_IMPORT_RECONCILIATION=PASS")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print("NEX_P2_04_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
