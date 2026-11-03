#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-portfolio-dashboard-accounts-ui.json"
P2_09_VERIFIER_PATH = ROOT / "scripts/verify_portfolio_api_export.py"
P2_09_FREEZE_PATH = ROOT / "artifacts/p2-09/portfolio-api-export-freeze.json"
P2_09_FREEZE_COMMIT = "bb5b500b67a6291df25c80f1f17fdceb9e20b14a"
P2_09_CANDIDATE_COMMIT = "13704691a091497d7cc26a09e3403b18246b0ec7"
P2_09_FREEZE_CHECKSUM = "25fc43678af53b565857a87983c5bc58b8d3df60bc22d24202876e6a285e3b1f"
CONTRACT_CHECKSUM = "b2d2199f267d4d375b37745e8c65dbf92b4a19ca489512f46bb5ea4a7656506a"

EXPECTED_EXPERIENCES = {
    "portfolio_overview",
    "valuation_health",
    "priced_position_allocation",
    "account_registry",
}
EXPECTED_OPERATIONS = {
    "GET /v1/assets",
    "GET /v1/portfolios",
    "GET /v1/accounts",
    "GET /v1/portfolios/{portfolio_id}/analytics?as_of={utc_timestamp}",
    "GET /v1/portfolios/{portfolio_id}/valuation-status?as_of={utc_timestamp}",
}
EXPECTED_STATES = {"loading", "ready", "empty", "error", "stale", "missing"}


class PortfolioDashboardAccountsContractError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PortfolioDashboardAccountsContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.relative_to(ROOT)} must contain an object")
    return payload


def canonical_checksum(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p2_09() -> None:
    spec = importlib.util.spec_from_file_location("verify_portfolio_api_export", P2_09_VERIFIER_PATH)
    _require(spec is not None and spec.loader is not None, "unable to load P2-09 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contract = module.load_contract()
    freeze = module.load_freeze_record()
    module.validate_frozen_p2_08()
    module.validate_contract(contract)
    module.validate_runtime_markers()
    module.validate_freeze_record(freeze, contract)
    module.validate_workflow()
    _require(canonical_checksum(freeze) == P2_09_FREEZE_CHECKSUM, "P2-09 Freeze record drift")
    _require(freeze.get("candidate_commit_sha") == P2_09_CANDIDATE_COMMIT, "P2-09 candidate drift")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(
        contract.get("schema_version") == "nexora-portfolio-dashboard-accounts-ui-contract-v1",
        "invalid P2-10 schema",
    )
    _require(contract.get("decision_id") == "NEX-P2-10", "invalid P2-10 decision")
    _require(contract.get("status") == "candidate", "P2-10 must remain a candidate before Freeze")

    prerequisite = contract.get("prerequisite")
    _require(isinstance(prerequisite, dict), "prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P2-09", "P2-09 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P2-09 prerequisite must be frozen")
    _require(prerequisite.get("freeze_commit_sha") == P2_09_FREEZE_COMMIT, "P2-09 Freeze commit drift")
    _require(
        prerequisite.get("accepted_candidate_commit_sha") == P2_09_CANDIDATE_COMMIT,
        "P2-09 candidate commit drift",
    )
    _require(
        prerequisite.get("freeze_record_path") == P2_09_FREEZE_PATH.relative_to(ROOT).as_posix(),
        "P2-09 Freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P2_09_FREEZE_CHECKSUM, "P2-09 checksum drift")
    _require(canonical_checksum(_json(P2_09_FREEZE_PATH)) == P2_09_FREEZE_CHECKSUM, "P2-09 record drift")

    scope = contract.get("scope")
    _require(isinstance(scope, dict), "scope must be an object")
    _require(set(scope.get("experiences", [])) == EXPECTED_EXPERIENCES, "experience inventory drift")
    _require(scope.get("locales") == ["fa", "en"], "locale inventory drift")
    _require(scope.get("persian_direction") == "rtl", "Persian direction drift")
    _require(scope.get("english_direction") == "ltr", "English direction drift")
    for required in ("existing_authenticated_shell", "responsive_desktop_tablet_mobile", "read_only_financial_ui"):
        _require(scope.get(required) is True, f"P2-10 scope requires {required}")
    for deferred in ("transaction_ui_included", "holdings_and_lots_ui_included", "reconciliation_ui_included"):
        _require(scope.get(deferred) is False, f"P2-10 cannot enable {deferred}")

    api = contract.get("api_boundary")
    _require(isinstance(api, dict), "API boundary must be an object")
    _require(set(api.get("operations", [])) == EXPECTED_OPERATIONS, "API operation inventory drift")
    for required in ("same_origin_api_only", "session_authentication_required", "owner_scope_derived_from_session"):
        _require(api.get(required) is True, f"API boundary requires {required}")
    _require(api.get("browser_cache_mode") == "no-store", "financial browser caching enabled")
    for forbidden in (
        "owner_id_accepted_from_browser",
        "direct_database_access",
        "direct_trd_bot_access",
        "new_backend_route_required",
    ):
        _require(api.get(forbidden) is False, f"API boundary enables {forbidden}")

    financial = contract.get("financial_presentation")
    _require(isinstance(financial, dict), "financial presentation must be an object")
    for required in (
        "canonical_decimal_strings_are_source",
        "exact_string_rounding_for_display",
        "nav_state_is_visible",
        "stale_state_is_visible",
        "missing_state_is_visible",
        "allocation_uses_priced_positions_only",
        "unpriced_positions_cannot_be_implied_as_zero",
        "as_of_timestamp_is_visible",
    ):
        _require(financial.get(required) is True, f"financial presentation requires {required}")
    for forbidden in ("binary_float_for_financial_amounts", "synthetic_or_demo_financial_values"):
        _require(financial.get(forbidden) is False, f"financial presentation enables {forbidden}")

    accounts = contract.get("account_registry_boundary")
    _require(isinstance(accounts, dict), "account registry boundary must be an object")
    for required in (
        "selected_portfolio_filter",
        "account_name",
        "account_kind",
        "institution_name",
        "lifecycle_status",
        "registry_key",
    ):
        _require(accounts.get(required) is True, f"account registry requires {required}")
    for forbidden in ("external_account_reference_rendered", "exchange_credentials_rendered", "account_mutation_ui"):
        _require(accounts.get(forbidden) is False, f"account registry enables {forbidden}")

    states = contract.get("state_model")
    _require(isinstance(states, dict), "state model must be an object")
    _require(set(states.get("states", [])) == EXPECTED_STATES, "dashboard state inventory drift")
    for required in (
        "registry_failure_preserves_no_mutation",
        "analytics_failure_keeps_account_registry_visible",
        "portfolio_selection_reloads_owner_scoped_details",
        "session_expiry_uses_existing_shell_recovery",
    ):
        _require(states.get(required) is True, f"state model requires {required}")

    accessibility = contract.get("accessibility")
    _require(isinstance(accessibility, dict), "accessibility must be an object")
    _require(accessibility.get("minimum_interactive_target_css_pixels") == 44, "touch target budget drift")
    for required in (
        "semantic_headings",
        "labelled_portfolio_selector",
        "keyboard_navigation",
        "visible_focus",
        "status_not_conveyed_by_color_only",
        "reduced_motion_respected",
    ):
        _require(accessibility.get(required) is True, f"accessibility requires {required}")
    _require(accessibility.get("mobile_horizontal_page_overflow") is False, "mobile page overflow enabled")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and security, "security boundary must be an object")
    _require(all(value is False for value in security.values()), "forbidden P2-10 capability enabled")
    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_candidate") is True, "P2-10 candidate is not ready")
    _require(transition.get("next_allowed_stage") == "NEX-P2-10-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P2-11", "post-Freeze stage drift")
    _require(
        transition.get("p2_11_before_transactions_holdings_reconciliation_ui") is True,
        "P2-11 UI boundary missing",
    )
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P2-10 contract checksum drift")


def validate_runtime_markers() -> None:
    component = (ROOT / "apps/web/src/components/portfolio-dashboard.tsx").read_text(encoding="utf-8")
    shell = (ROOT / "apps/web/src/components/authenticated-shell.tsx").read_text(encoding="utf-8")
    client = (ROOT / "apps/web/src/lib/api-client.ts").read_text(encoding="utf-8")
    styles = (ROOT / "apps/web/src/app/globals.css").read_text(encoding="utf-8")
    english = _json(ROOT / "apps/web/messages/en.json")
    persian = _json(ROOT / "apps/web/messages/fa.json")
    browser = (ROOT / "apps/web/tests/e2e/authenticated-shell.spec.ts").read_text(encoding="utf-8")

    for marker in (
        "export function PortfolioDashboard",
        'apiRequest<ListResponse<Portfolio>>("/api/v1/portfolios"',
        'apiRequest<ListResponse<Account>>("/api/v1/accounts"',
        'apiRequest<ListResponse<Asset>>("/api/v1/assets"',
        "/analytics?as_of=",
        "/valuation-status?as_of=",
        "function parseDecimal",
        "BigInt(",
        "allocationRows(",
        'details.analytics.state !== "complete"',
        'id="accounts"',
    ):
        _require(marker in component, f"dashboard runtime marker missing: {marker}")
    for forbidden in ("external_reference", 'method: "POST"', "owner_id"):
        _require(forbidden not in component, f"dashboard renders or sends forbidden field: {forbidden}")
    _require("<PortfolioDashboard dictionary={dictionary} locale={locale} />" in shell, "dashboard is not composed")
    _require('href={index === 0 ? `/${locale}` : "#accounts"}' in shell, "account navigation is not enabled")
    for marker in ('cache: "no-store"', 'credentials: "same-origin"', "signal: options.signal"):
        _require(marker in client, f"API client marker missing: {marker}")
    for marker in (".portfolio-metric-grid", ".portfolio-detail-grid", ".account-grid", "min-height: 2.75rem"):
        _require(marker in styles, f"responsive dashboard style missing: {marker}")
    for locale, dictionary in (("en", english), ("fa", persian)):
        dashboard = dictionary.get("portfolioDashboard")
        _require(isinstance(dashboard, dict), f"{locale} dashboard dictionary missing")
        for key in ("title", "valuationHealth", "allocation", "accountRegistry", "analyticsState"):
            _require(key in dashboard, f"{locale} dashboard dictionary key missing: {key}")
    for marker in (
        "Persian authenticated shell is RTL and responsive",
        'name: "نمای کلی پورتفولیو"',
        'name: "دفتر حساب‌ها"',  # noqa: RUF001
    ):
        _require(marker in browser, f"browser acceptance marker missing: {marker}")


def validate_workflow() -> None:
    workflow = (ROOT / ".github/workflows/portfolio-dashboard-accounts.yml").read_text(encoding="utf-8")
    for marker in (
        "python3 scripts/verify_portfolio_dashboard_accounts.py",
        "python3 -m unittest discover -s tests -v",
        "pnpm format:check",
        "pnpm lint",
        "pnpm typecheck",
        "pnpm test",
        "pnpm build",
        "playwright install --with-deps chromium",
        "test:e2e",
    ):
        _require(marker in workflow, f"P2-10 workflow marker missing: {marker}")


def main() -> int:
    validate_frozen_p2_09()
    contract = load_contract()
    validate_contract(contract)
    validate_runtime_markers()
    validate_workflow()
    print("NEX_P2_09_PREREQUISITE=PASS")
    print("NEX_P2_10_PORTFOLIO_DASHBOARD_ACCOUNTS_UI=PASS")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print(f"p2_09_freeze_checksum={P2_09_FREEZE_CHECKSUM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
