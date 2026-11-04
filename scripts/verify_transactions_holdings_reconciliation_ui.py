#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-transactions-holdings-reconciliation-ui.json"
FREEZE_PATH = ROOT / "artifacts/p2-11/transactions-holdings-reconciliation-ui-freeze.json"
P2_10_VERIFIER_PATH = ROOT / "scripts/verify_portfolio_dashboard_accounts.py"
P2_10_FREEZE_PATH = ROOT / "artifacts/p2-10/portfolio-dashboard-accounts-ui-freeze.json"
P2_10_FREEZE_COMMIT = "d2a6df0b26b914e5a012b77ad452605af587c940"
P2_10_CANDIDATE_COMMIT = "949643fc3cd945c0c25b1089428c4c72ce794b3b"
P2_10_FREEZE_CHECKSUM = "9d160d1bf4f12f609bd3fd757e709231bf8403655261fa82be72f35c57becad3"
CONTRACT_CHECKSUM = "b9533c6d3d9ea74bb60272904a517350b95a291c113aa82ebcaf69a1a6b508cf"
CANDIDATE_SHA = "ef65e02e2d257b0f69277db19e96d23443b77ef2"
CANDIDATE_TREE_SHA = "d4f86a91a8b8e17d86fc30e3b8266bd73713fc05"
CANDIDATE_MESSAGE = "feat(nexora): add transactions holdings reconciliation UI"
CANDIDATE_PREDECESSOR = "d2a6df0b26b914e5a012b77ad452605af587c940"
CANDIDATE_LINEAGE_CHECKSUM = "468ba4bf63ed4028f1f15c2328236aeda390d9bf7edec2713b632138aa9658e3"
EXPECTED_WORKFLOW_RUNS = 26
EXPECTED_CHECKS = 86
WORKFLOW_RUNS_CHECKSUM = "25388c93b1295c22db58356f221c9836032181e2260cfed95170d7243f62f101"
CHECKS_CHECKSUM = "78e9182466cb6cde97a29f731ac43b9a3db29ac90bbb12f3a661fe6e32b4f688"
P2_11_WORKFLOW_RUN_ID = 41790624066

EXPECTED_EXPERIENCES = {
    "immutable_transaction_journal",
    "holdings_projection",
    "cost_basis_lots",
    "import_dry_run_preview",
    "import_review_and_atomic_publication",
    "reconciliation_decisions",
}
EXPECTED_OPERATIONS = {
    "GET /v1/transactions?portfolio_id={portfolio_id}",
    "GET /v1/portfolios/{portfolio_id}/holdings?cost_basis_method={method}",
    "GET /v1/portfolios/{portfolio_id}/lots?cost_basis_method={method}",
    "POST /v1/portfolios/{portfolio_id}/holdings/rebuilds",
    "POST /v1/imports/dry-runs",
    "GET /v1/imports",
    "POST /v1/imports/{import_batch_id}/reviews",
    "POST /v1/imports/{import_batch_id}/publication",
    "GET /v1/reconciliation-cases",
    "POST /v1/reconciliation-cases/{reconciliation_case_id}/decisions",
}
EXPECTED_STATES = {
    "loading",
    "ready",
    "empty",
    "error",
    "projection_missing",
    "mutation_pending",
    "reauthentication_required",
}
EXPECTED_RECONCILIATION_STATES = {
    "open",
    "matched",
    "accepted_difference",
    "resolved",
    "ignored_with_reason",
}


class TransactionsHoldingsReconciliationUiContractError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TransactionsHoldingsReconciliationUiContractError(message)


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


def validate_frozen_p2_10() -> None:
    spec = importlib.util.spec_from_file_location("verify_portfolio_dashboard_accounts", P2_10_VERIFIER_PATH)
    _require(spec is not None and spec.loader is not None, "unable to load P2-10 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contract = module.load_contract()
    freeze = module.load_freeze_record()
    module.validate_frozen_p2_09()
    module.validate_contract(contract)
    module.validate_runtime_markers()
    module.validate_freeze_record(freeze, contract)
    module.validate_workflow()
    _require(canonical_checksum(freeze) == P2_10_FREEZE_CHECKSUM, "P2-10 Freeze record drift")
    _require(freeze.get("candidate_commit_sha") == P2_10_CANDIDATE_COMMIT, "P2-10 candidate drift")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(
        contract.get("schema_version") == "nexora-transactions-holdings-reconciliation-ui-contract-v1",
        "invalid P2-11 schema",
    )
    _require(contract.get("decision_id") == "NEX-P2-11", "invalid P2-11 decision")
    _require(contract.get("status") == "candidate", "P2-11 must remain a candidate before Freeze")

    prerequisite = contract.get("prerequisite")
    _require(isinstance(prerequisite, dict), "prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-10", "P2-10 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P2-10 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_10_FREEZE_COMMIT, "P2-10 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_10_CANDIDATE_COMMIT,
        "P2-10 candidate commit drift",
    )
    _require(
        prerequisite.get("freeze_record_path") == P2_10_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-10 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_10_FREEZE_CHECKSUM, "P2-10 checksum drift")
    _require(canonical_checksum(_json(P2_10_FREEZE_PATH)) == P2_10_FREEZE_CHECKSUM, "P2-10 record drift")

    scope = contract.get("scope")
    _require(isinstance(scope, dict), "scope must be an object")
    _require(set(scope.get("experiences", [])) == EXPECTED_EXPERIENCES, "experience inventory drift")
    _require(scope.get("locales") == ["fa", "en"], "locale inventory drift")
    _require(scope.get("persian_direction") == "rtl", "Persian direction drift")
    _require(scope.get("english_direction") == "ltr", "English direction drift")
    for required in ("existing_authenticated_shell", "responsive_desktop_tablet_mobile"):
        _require(scope.get(required) is True, f"P2-11 scope requires {required}")
    for forbidden in (
        "journal_mutation_ui_included",
        "automatic_journal_correction",
        "account_mutation_ui_included",
    ):
        _require(scope.get(forbidden) is False, f"P2-11 scope enables {forbidden}")

    api = contract.get("api_boundary")
    _require(isinstance(api, dict), "API boundary must be an object")
    _require(set(api.get("operations", [])) == EXPECTED_OPERATIONS, "API operation inventory drift")
    for required in (
        "same_origin_api_only",
        "session_authentication_required",
        "owner_scope_derived_from_session",
        "csrf_for_mutations",
        "recent_reauthentication_for_publication_and_decisions",
    ):
        _require(api.get(required) is True, f"API boundary requires {required}")
    _require(api.get("browser_cache_mode") == "no-store", "financial browser caching enabled")
    for forbidden in (
        "owner_id_accepted_from_browser",
        "direct_database_access",
        "direct_trd_bot_access",
        "new_backend_route_required",
    ):
        _require(api.get(forbidden) is False, f"API boundary enables {forbidden}")

    journal = contract.get("journal_presentation")
    _require(isinstance(journal, dict), "journal presentation must be an object")
    for required in (
        "append_only_evidence_visible",
        "balanced_legs_visible",
        "source_lineage_visible",
        "correction_kind_visible",
        "canonical_decimal_strings_visible",
    ):
        _require(journal.get(required) is True, f"journal presentation requires {required}")
    for forbidden in ("binary_float_for_financial_amounts", "in_place_edit", "physical_delete"):
        _require(journal.get(forbidden) is False, f"journal presentation enables {forbidden}")

    holdings = contract.get("holdings_and_lots")
    _require(isinstance(holdings, dict), "holdings and lots boundary must be an object")
    _require(holdings.get("cost_basis_methods") == ["fifo", "weighted_average"], "cost-basis policy drift")
    for required in (
        "explicit_rebuild_action",
        "projection_version_visible",
        "journal_sha256_visible",
        "journal_transaction_count_visible",
        "known_mixed_unknown_basis_visible",
        "missing_projection_is_not_zero",
    ):
        _require(holdings.get(required) is True, f"holdings presentation requires {required}")
    _require(
        holdings.get("derived_projection_presented_as_source_of_truth") is False,
        "derived projection presented as journal source of truth",
    )

    imports = contract.get("import_workflow")
    _require(isinstance(imports, dict), "import workflow must be an object")
    _require(imports.get("formats") == ["csv", "nexora_json"], "import format inventory drift")
    _require(imports.get("maximum_content_bytes") == 1_048_576, "import content budget drift")
    for required in (
        "dry_run_required",
        "normalized_row_preview",
        "duplicate_count_visible",
        "quarantine_count_visible",
        "content_sha256_visible",
        "owner_review_reason_required",
        "atomic_publication",
    ):
        _require(imports.get(required) is True, f"import workflow requires {required}")
    for forbidden in ("partial_publication", "quarantined_batch_publication"):
        _require(imports.get(forbidden) is False, f"import workflow enables {forbidden}")

    reconciliation = contract.get("reconciliation_workflow")
    _require(isinstance(reconciliation, dict), "reconciliation workflow must be an object")
    _require(
        set(reconciliation.get("states", [])) == EXPECTED_RECONCILIATION_STATES,
        "reconciliation state inventory drift",
    )
    for required in ("owner_reason_required", "optimistic_row_version_sent", "append_only_decision_evidence"):
        _require(reconciliation.get(required) is True, f"reconciliation requires {required}")
    for forbidden in ("automatic_destructive_fix", "automatic_journal_correction"):
        _require(reconciliation.get(forbidden) is False, f"reconciliation enables {forbidden}")

    states = contract.get("state_model")
    _require(isinstance(states, dict), "state model must be an object")
    _require(set(states.get("states", [])) == EXPECTED_STATES, "UI state inventory drift")
    for required in (
        "portfolio_selection_reloads_owner_scoped_evidence",
        "failed_mutation_preserves_visible_evidence",
        "sensitive_actions_fail_closed",
        "session_expiry_uses_existing_shell_recovery",
    ):
        _require(states.get(required) is True, f"state model requires {required}")

    accessibility = contract.get("accessibility")
    _require(isinstance(accessibility, dict), "accessibility must be an object")
    _require(accessibility.get("minimum_interactive_target_css_pixels") == 44, "touch target budget drift")
    for required in (
        "semantic_headings",
        "aria_tablist",
        "labelled_forms",
        "keyboard_navigation",
        "visible_focus",
        "status_not_conveyed_by_color_only",
        "reduced_motion_respected",
    ):
        _require(accessibility.get(required) is True, f"accessibility requires {required}")
    _require(accessibility.get("mobile_horizontal_page_overflow") is False, "mobile page overflow enabled")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and security, "security boundary must be an object")
    _require(all(value is False for value in security.values()), "forbidden P2-11 capability enabled")
    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_candidate") is True, "P2-11 candidate is not ready")
    _require(transition.get("next_allowed_stage") == "NEX-P2-11-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P2-12", "post-Freeze stage drift")
    _require(transition.get("p2_12_before_phase_two_acceptance") is True, "P2-12 acceptance boundary missing")
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-11 contract checksum drift")


def validate_runtime_markers() -> None:
    component = (ROOT / "apps/web/src/components/portfolio-operations.tsx").read_text(encoding="utf-8")
    dashboard = (ROOT / "apps/web/src/components/portfolio-dashboard.tsx").read_text(encoding="utf-8")
    shell = (ROOT / "apps/web/src/components/authenticated-shell.tsx").read_text(encoding="utf-8")
    client = (ROOT / "apps/web/src/lib/api-client.ts").read_text(encoding="utf-8")
    styles = (ROOT / "apps/web/src/app/globals.css").read_text(encoding="utf-8")
    english = _json(ROOT / "apps/web/messages/en.json")
    persian = _json(ROOT / "apps/web/messages/fa.json")
    browser = (ROOT / "apps/web/tests/e2e/authenticated-shell.spec.ts").read_text(encoding="utf-8")

    for marker in (
        "export function PortfolioOperations",
        "/api/v1/transactions?portfolio_id=",
        "/holdings?cost_basis_method=",
        "/lots?cost_basis_method=",
        "/holdings/rebuilds",
        '"/api/v1/imports/dry-runs"',
        '"/api/v1/imports"',
        "/reviews",
        "/publication",
        '"/api/v1/reconciliation-cases"',
        "/decisions",
        "expected_row_version: item.row_version",
        "recentlyReauthenticated",
        "JSON.stringify(row.normalized_payload, null, 2)",
        'role="tablist"',
        "function exactDecimal",
    ):
        _require(marker in component, f"P2-11 runtime marker missing: {marker}")
    for forbidden in ("owner_id", "external_reference", "parseFloat(", "Number(holding", "Number(lot"):
        _require(forbidden not in component, f"P2-11 runtime includes forbidden marker: {forbidden}")
    _require("export type PortfolioWorkspaceContext" in dashboard, "portfolio context is not shared")
    _require("onWorkspaceChange?.(workspaceContext)" in dashboard, "portfolio selection is not propagated")
    _require("<PortfolioOperations" in shell, "P2-11 workspace is not composed")
    _require("recentlyReauthenticated={session.recently_reauthenticated}" in shell, "reauth state is not bound")
    _require('"#portfolio-operations"' in shell, "journal navigation is not enabled")
    _require("index === 4" in shell, "journal navigation does not target the Journal item")
    for marker in ('cache: "no-store"', 'credentials: "same-origin"', 'headers.set("X-CSRF-Token", csrf)'):
        _require(marker in client, f"API client marker missing: {marker}")
    for marker in (
        ".portfolio-operations",
        ".operations-tabs",
        ".responsive-data-grid",
        ".decision-form",
        "min-height: 2.75rem",
    ):
        _require(marker in styles, f"responsive P2-11 style missing: {marker}")
    for locale, dictionary in (("en", english), ("fa", persian)):
        operations = dictionary.get("portfolioOperations")
        _require(isinstance(operations, dict), f"{locale} P2-11 dictionary missing")
        for key in ("title", "tabs", "journal", "holdings", "imports", "reconciliation"):
            _require(key in operations, f"{locale} P2-11 dictionary key missing: {key}")
    for marker in (
        "Persian authenticated shell is RTL and responsive",
        'name: "ژورنال، دارایی‌ها و تطبیق"',  # noqa: RUF001
        'name: "ژورنال"',
        'page.getByText("Opening evidence")',
    ):
        _require(marker in browser, f"P2-11 browser acceptance marker missing: {marker}")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(
        record.get("schema_version") == "nexora-transactions-holdings-reconciliation-ui-freeze-v1",
        "invalid P2-11 Freeze schema",
    )
    _require(record.get("decision_id") == "NEX-P2-11", "invalid P2-11 Freeze decision")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "Freeze repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_tree_sha") == CANDIDATE_TREE_SHA, "candidate tree drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "candidate message drift")
    _require(record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR, "candidate predecessor drift")

    lineage = record.get("candidate_lineage")
    _require(isinstance(lineage, list), "candidate lineage must be an array")
    _require(len(lineage) == 1, "P2-11 candidate lineage must contain one implementation commit")
    _require(canonical_checksum(lineage) == CANDIDATE_LINEAGE_CHECKSUM, "candidate lineage drift")
    _require(lineage[0].get("sha") == CANDIDATE_SHA, "candidate lineage does not end at accepted SHA")
    _require(lineage[0].get("parent_sha") == CANDIDATE_PREDECESSOR, "candidate lineage base drift")

    workflows = record.get("workflow_runs")
    _require(isinstance(workflows, list), "workflow runs must be an array")
    _require(len(workflows) == EXPECTED_WORKFLOW_RUNS, "workflow run inventory drift")
    _require(canonical_checksum(workflows) == WORKFLOW_RUNS_CHECKSUM, "workflow run evidence drift")
    run_ids = {workflow.get("run_id") for workflow in workflows}
    _require(len(run_ids) == EXPECTED_WORKFLOW_RUNS, "workflow run IDs must be unique")
    for workflow in workflows:
        _require(workflow.get("event") == "push", "workflow event drift")
        _require(workflow.get("head_sha") == CANDIDATE_SHA, "workflow candidate SHA drift")
        _require(workflow.get("run_attempt") == 1, "workflow attempt drift")
        _require(workflow.get("conclusion") == "success", "workflow did not succeed")

    checks = record.get("checks")
    _require(isinstance(checks, list), "checks must be an array")
    _require(len(checks) == EXPECTED_CHECKS, "check inventory drift")
    _require(canonical_checksum(checks) == CHECKS_CHECKSUM, "check evidence drift")
    job_ids = {check.get("job_id") for check in checks}
    _require(len(job_ids) == EXPECTED_CHECKS, "check job IDs must be unique")
    _require(all(check.get("run_id") in run_ids for check in checks), "check references an unknown workflow")
    _require(all(check.get("conclusion") == "success" for check in checks), "check did not succeed")
    _require(
        record.get("check_summary") == {"total": 86, "successful": 86, "failed": 0, "pending": 0},
        "check summary drift",
    )
    p2_11_jobs = {check.get("name") for check in checks if check.get("run_id") == P2_11_WORKFLOW_RUN_ID}
    _require(
        p2_11_jobs == {"web", "browser", "backend-regression", "portfolio-operations-contract"},
        "P2-11 primary job inventory drift",
    )

    contract_evidence = record.get("transactions_holdings_reconciliation_ui_contract")
    _require(isinstance(contract_evidence, dict), "P2-11 contract evidence must be an object")
    _require(contract_evidence.get("schema_version") == contract.get("schema_version"), "contract schema drift")
    _require(contract_evidence.get("path") == CONTRACT_PATH.relative_to(ROOT).as_posix(), "contract path drift")
    _require(contract_evidence.get("checksum") == canonical_checksum(contract), "contract evidence drift")
    _require(contract_evidence.get("checksum") == CONTRACT_CHECKSUM, "contract checksum drift")

    prerequisite = record.get("p2_10_prerequisite")
    _require(isinstance(prerequisite, dict), "P2-10 prerequisite evidence must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-10", "P2-10 decision drift")
    _require(prerequisite.get("frozen") is True, "P2-10 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_10_FREEZE_COMMIT, "P2-10 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_10_CANDIDATE_COMMIT,
        "P2-10 candidate drift",
    )
    _require(
        prerequisite.get("freeze_record_path") == P2_10_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-10 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_10_FREEZE_CHECKSUM, "P2-10 checksum drift")

    _require(record.get("recorded_on") == "2026-11-04", "Freeze record date drift")
    _require(record.get("frozen") is True, "P2-11 must be frozen")
    for completed in (
        "immutable_transaction_journal_ui_complete",
        "holdings_projection_ui_complete",
        "cost_basis_lots_ui_complete",
        "import_dry_run_preview_complete",
        "import_review_and_atomic_publication_complete",
        "reconciliation_decisions_complete",
        "bilingual_rtl_ltr_complete",
        "responsive_accessibility_complete",
        "chromium_browser_acceptance_complete",
    ):
        _require(record.get(completed) is True, f"Freeze completion missing: {completed}")
    for deferred in (
        "phase_two_acceptance_complete",
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
        "journal_in_place_edit",
        "journal_physical_delete",
        "automatic_journal_correction",
        "partial_import_publication",
        "quarantined_batch_publication",
    ):
        _require(record.get(forbidden) is False, f"Freeze enables forbidden capability: {forbidden}")
    _require(record.get("next_allowed_stage") == "NEX-P2-12", "Freeze next stage drift")


def validate_workflow() -> None:
    workflow = (ROOT / ".github/workflows/transactions-holdings-reconciliation-ui.yml").read_text(encoding="utf-8")
    for marker in (
        "python3 scripts/verify_portfolio_dashboard_accounts.py",
        "python3 scripts/verify_transactions_holdings_reconciliation_ui.py",
        "python3 -m unittest discover -s tests -v",
        "pnpm format:check",
        "pnpm lint",
        "pnpm typecheck",
        "pnpm test",
        "pnpm build",
        "playwright install --with-deps chromium",
        "test:e2e",
    ):
        _require(marker in workflow, f"P2-11 workflow marker missing: {marker}")


def main() -> int:
    validate_frozen_p2_10()
    contract = load_contract()
    freeze_record = load_freeze_record()
    validate_contract(contract)
    validate_runtime_markers()
    validate_freeze_record(freeze_record, contract)
    validate_workflow()
    print("NEX_P2_10_PREREQUISITE=PASS")
    print("NEX_P2_11_TRANSACTIONS_HOLDINGS_RECONCILIATION_UI=PASS")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print(f"p2_10_freeze_checksum={P2_10_FREEZE_CHECKSUM}")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print("NEX_P2_11_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
