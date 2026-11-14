#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-transaction-journal.json"
FREEZE_PATH = ROOT / "artifacts/p2-03/transaction-journal-freeze.json"
P2_02_CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-portfolio-registry.json"
P2_02_FREEZE_PATH = ROOT / "artifacts/p2-02/portfolio-registry-freeze.json"
P2_02_VERIFIER_PATH = ROOT / "scripts/verify_portfolio_registry.py"
P2_02_FREEZE_COMMIT = "db6566bc0713a8c9822f52d2b895f790440a3621"
P2_02_CANDIDATE_COMMIT = "add7a7eec7226ecc62989b23cccf380c32e678d7"
P2_02_FREEZE_CHECKSUM = "d4b549c07cb3596b3de36a73cb658a2bb7a7a8efa74d84e693179e15134e65bf"
CONTRACT_CHECKSUM = "0a197692e311c98c91fe0eea854beb11ab7cf1df2c990b6a386066dee2414d6f"
CANDIDATE_SHA = "cf3ddd90eed968a4f672e78866338d97e68e3e25"
CANDIDATE_TREE_SHA = "6b9d1d5f3e8cc3ab57ace4d2dcf89f773c696e60"
CANDIDATE_MESSAGE = "feat(nexora): add immutable transaction journal"
CANDIDATE_PREDECESSOR = "db6566bc0713a8c9822f52d2b895f790440a3621"
CANDIDATE_LINEAGE_CHECKSUM = "2035da64c9a3dbb9da7467ed42cb1e421779de35cf7ec0e67577d1b52e721451"
WORKFLOW_RUNS_CHECKSUM = "819db0d373f7a94b0e03c925b3caa28f5e091b913f5e2a7f7624b1406e240537"
CHECKS_CHECKSUM = "09a4bf6d95bad9c601b2d17f5b36eb2ad11fa2ff756769dbb53072657e5af786"
EXPECTED_WORKFLOW_RUNS = 18
EXPECTED_CHECKS = 60

EXPECTED_KINDS = {
    "buy",
    "sell",
    "deposit",
    "withdrawal",
    "transfer",
    "fee",
    "income",
    "reward",
    "airdrop",
    "adjustment",
    "opening_balance",
}
EXPECTED_OPERATIONS = {
    "POST /v1/transactions",
    "GET /v1/transactions",
    "GET /v1/transactions/{transaction_id}",
    "POST /v1/transactions/{transaction_id}/reversals",
    "POST /v1/transactions/{transaction_id}/supersessions",
}
FORBIDDEN_CAPABILITIES = {
    "exchange_credentials",
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


class TransactionJournalContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TransactionJournalContractError(message)


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


def validate_frozen_p2_02() -> None:
    spec = importlib.util.spec_from_file_location("verify_portfolio_registry", P2_02_VERIFIER_PATH)
    _require(spec is not None and spec.loader is not None, "unable to load P2-02 verifier")
    if spec is None or spec.loader is None:
        raise TransactionJournalContractError("unable to load P2-02 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contract = module.load_contract(P2_02_CONTRACT_PATH)
    freeze = module.load_freeze_record(P2_02_FREEZE_PATH)
    module.validate_frozen_p2_01()
    module.validate_contract(contract)
    module.validate_runtime_markers()
    module.validate_freeze_record(freeze, contract)
    module.validate_freeze_workflow()
    _require(canonical_checksum(freeze) == P2_02_FREEZE_CHECKSUM, "P2-02 Freeze artifact drift")
    _require(freeze.get("frozen") is True, "P2-02 prerequisite is not frozen")
    _require(freeze.get("next_allowed_stage") == "NEX-P2-03", "P2-02 does not open P2-03")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-transaction-journal-contract-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P2-03", "invalid decision")
    _require(contract.get("decision_date") == "2026-10-31", "invalid decision date")
    _require(contract.get("status") == "candidate", "P2-03 must remain candidate before Freeze")

    prerequisite = contract.get("prerequisite")
    _require(isinstance(prerequisite, dict), "prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-02", "P2-02 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P2-02 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_02_FREEZE_COMMIT, "P2-02 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_02_CANDIDATE_COMMIT,
        "P2-02 candidate drift",
    )
    _require(
        prerequisite.get("freeze_record_path") == P2_02_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-02 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_02_FREEZE_CHECKSUM, "P2-02 checksum drift")

    scope = contract.get("scope")
    _require(isinstance(scope, dict), "scope must be an object")
    _require(scope.get("entities") == ["transaction", "transaction_leg"], "journal entity drift")
    _require(set(scope.get("transaction_kinds", [])) == EXPECTED_KINDS, "transaction kind drift")
    _require(set(scope.get("source_kinds", [])) == {"manual", "import", "trd_bot"}, "source kind drift")
    _require(set(scope.get("correction_kinds", [])) == {"reversal", "supersession"}, "correction kind drift")
    for deferred in (
        "holdings_projection_included",
        "lots_included",
        "cost_basis_included",
        "valuation_included",
        "pnl_included",
        "import_runtime_included",
    ):
        _require(scope.get(deferred) is False, f"P2-03 cannot include {deferred}")

    journal = contract.get("journal_invariants")
    _require(isinstance(journal, dict), "journal_invariants must be an object")
    _require(journal.get("minimum_legs") == 2, "minimum leg count drift")
    _require(journal.get("balance_scope") == "zero_sum_per_asset", "balance policy drift")
    _require(journal.get("maximum_decimal_places") == 30, "decimal scale drift")
    _require(journal.get("maximum_decimal_digits") == 60, "decimal precision drift")
    for invariant in (
        "append_only",
        "database_update_delete_rejected",
        "owner_account_leg_required",
        "account_or_external_counterparty_exclusive",
        "owner_scope_on_transactions_and_legs",
        "portfolio_scope_required",
        "occurred_at_required",
        "recorded_at_required",
        "idempotency_key_required",
        "request_checksum_required",
        "source_lineage_required",
        "source_payload_checksum_required",
        "exact_decimal_strings_at_api",
        "binary_float_forbidden",
        "asset_precision_enforced",
    ):
        _require(journal.get(invariant) is True, f"journal invariant requires {invariant}")

    correction = contract.get("correction_policy")
    _require(isinstance(correction, dict), "correction_policy must be an object")
    for forbidden in ("in_place_edit", "physical_delete", "cross_owner_correction", "cross_portfolio_correction"):
        _require(correction.get(forbidden) is False, f"correction policy forbids {forbidden}")
    for required in (
        "reversal_legs_derived_from_target",
        "supersession_creates_new_balanced_transaction",
        "owner_reason_required",
        "single_direct_correction_per_transaction",
    ):
        _require(correction.get(required) is True, f"correction policy requires {required}")

    persistence = contract.get("persistence")
    _require(isinstance(persistence, dict), "persistence must be an object")
    _require(persistence.get("migration_revision") == "20261031_0007", "migration revision drift")
    _require(
        persistence.get("tables") == ["nexora.transactions", "nexora.transaction_legs"],
        "journal table inventory drift",
    )
    for invariant in (
        "account_owner_composite_key_added",
        "composite_owner_foreign_keys",
        "immutable_database_triggers",
        "postgresql_concurrency_required",
        "upgrade_downgrade_rebuild_drift_cycle_required",
    ):
        _require(persistence.get(invariant) is True, f"persistence requires {invariant}")

    runtime = contract.get("runtime_api")
    _require(isinstance(runtime, dict), "runtime_api must be an object")
    _require(runtime.get("authentication") == "opaque_owner_session", "authentication drift")
    _require(runtime.get("owner_id_accepted_from_request") is False, "owner override is forbidden")
    _require(runtime.get("csrf_for_mutations") is True, "CSRF protection is required")
    _require(runtime.get("idempotency_header") == "Idempotency-Key", "idempotency header drift")
    _require(runtime.get("unknown_fields_rejected") is True, "unknown fields must be rejected")
    _require(set(runtime.get("operations", [])) == EXPECTED_OPERATIONS, "API operation inventory drift")
    _require(runtime.get("update_operation_exposed") is False, "journal update API is forbidden")
    _require(runtime.get("delete_operation_exposed") is False, "journal delete API is forbidden")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security_boundary must be an object")
    _require(set(security) == FORBIDDEN_CAPABILITIES, "security capability inventory drift")
    for capability in FORBIDDEN_CAPABILITIES:
        _require(security.get(capability) is False, f"forbidden capability enabled: {capability}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_candidate") is True, "P2-03 is not ready for candidate")
    _require(transition.get("next_allowed_stage") == "NEX-P2-03-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P2-04", "post-Freeze stage drift")
    _require(transition.get("freeze_before_import_runtime") is True, "P2-04 must remain blocked")


def validate_runtime_markers() -> None:
    models = (ROOT / "apps/server/src/nexora/adapters/postgresql/models.py").read_text(encoding="utf-8")
    repository = (ROOT / "apps/server/src/nexora/adapters/postgresql/transaction_journal.py").read_text(
        encoding="utf-8"
    )
    domain = (ROOT / "apps/server/src/nexora/transaction_journal.py").read_text(encoding="utf-8")
    api = (ROOT / "apps/server/src/nexora/api.py").read_text(encoding="utf-8")
    migration = (ROOT / "alembic/versions/20261031_0007_immutable_transaction_journal.py").read_text(encoding="utf-8")
    for marker in ("class TransactionRecord", "class TransactionLegRecord", "Numeric(60, 30)"):
        _require(marker in models, f"missing journal model marker: {marker}")
    for marker in (
        "class TransactionJournalRepository",
        "def post_transaction",
        "def reverse_transaction",
        "def supersede_transaction",
        "request_sha256",
    ):
        _require(marker in repository, f"missing journal repository marker: {marker}")
    for marker in ("validate_balanced_legs", "zero for every asset", "canonical_quantity"):
        _require(marker in domain, f"missing journal domain marker: {marker}")
    for operation in (
        '"/v1/transactions"',
        '"/v1/transactions/{transaction_id}"',
        '"/v1/transactions/{transaction_id}/reversals"',
        '"/v1/transactions/{transaction_id}/supersessions"',
    ):
        _require(operation in api, f"missing journal API marker: {operation}")
    for marker in (
        'revision: str = "20261031_0007"',
        "reject_transaction_journal_mutation",
        "BEFORE UPDATE OR DELETE",
    ):
        _require(marker in migration, f"missing immutable migration marker: {marker}")

    openapi = _json(ROOT / "contracts/runtime/v1/openapi.json")
    operations = {
        f"{method.upper()} {path}"
        for path, path_item in openapi["paths"].items()
        for method in path_item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    _require(operations >= EXPECTED_OPERATIONS, "P2-03 OpenAPI operation inventory drift")
    _require(
        not any(
            operation.startswith(("PUT /v1/transactions", "PATCH /v1/transactions", "DELETE /v1/transactions"))
            for operation in operations
        ),
        "mutable journal API operation exposed",
    )


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-transaction-journal-freeze-v1", "invalid Freeze schema")
    _require(record.get("decision_id") == "NEX-P2-03", "invalid Freeze decision")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "Freeze repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_tree_sha") == CANDIDATE_TREE_SHA, "candidate tree drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "candidate message drift")
    _require(record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR, "candidate predecessor drift")

    lineage = record.get("candidate_lineage")
    _require(isinstance(lineage, list), "candidate lineage must be an array")
    _require(len(lineage) == 1, "candidate lineage must contain the P2-03 candidate")
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
        record.get("check_summary") == {"total": 60, "successful": 60, "failed": 0, "pending": 0},
        "check summary drift",
    )

    contract_evidence = record.get("transaction_journal_contract")
    _require(isinstance(contract_evidence, dict), "transaction journal evidence must be an object")
    _require(
        contract_evidence.get("schema_version") == contract.get("schema_version"),
        "transaction journal schema drift",
    )
    _require(contract_evidence.get("path") == CONTRACT_PATH.relative_to(ROOT).as_posix(), "contract path drift")
    _require(contract_evidence.get("checksum") == canonical_checksum(contract), "contract evidence drift")
    _require(contract_evidence.get("checksum") == CONTRACT_CHECKSUM, "contract checksum drift")

    prerequisite = record.get("p2_02_prerequisite")
    _require(isinstance(prerequisite, dict), "P2-02 prerequisite evidence must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-02", "P2-02 decision drift")
    _require(prerequisite.get("frozen") is True, "P2-02 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_02_FREEZE_COMMIT, "P2-02 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_02_CANDIDATE_COMMIT,
        "P2-02 candidate drift",
    )
    _require(
        prerequisite.get("freeze_record_path") == P2_02_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-02 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_02_FREEZE_CHECKSUM, "P2-02 checksum drift")

    _require(record.get("recorded_on") == "2026-10-31", "Freeze record date drift")
    _require(record.get("frozen") is True, "P2-03 must be frozen")
    _require(record.get("transaction_journal_complete") is True, "journal completion evidence missing")
    for deferred in (
        "portfolio_product_complete",
        "holdings_projection_complete",
        "import_reconciliation_complete",
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
    _require(record.get("next_allowed_stage") == "NEX-P2-04", "Freeze next stage drift")


def validate_freeze_workflow() -> None:
    workflow = (ROOT / ".github/workflows/transaction-journal.yml").read_text(encoding="utf-8")
    for marker in (
        "Verify frozen P2-02 prerequisite",
        "Verify P2-03 transaction journal contract",
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
        _require(marker in workflow, f"P2-03 workflow evidence missing: {marker}")


def main() -> int:
    validate_frozen_p2_02()
    contract = load_contract()
    freeze_record = load_freeze_record()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-03 contract checksum drift")
    validate_runtime_markers()
    validate_freeze_record(freeze_record, contract)
    validate_freeze_workflow()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P2_02_PREREQUISITE=PASS")
    print("NEX_P2_03_TRANSACTION_JOURNAL=PASS")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print("NEX_P2_03_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
