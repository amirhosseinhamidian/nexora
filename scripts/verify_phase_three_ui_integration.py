#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-three-ui-integration.json"
P3_11_CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-phase-three-export-coverage.json"
WORKSPACE_PATH = ROOT / "apps/web/src/components/workspace-view.tsx"
NAVIGATION_PATH = ROOT / "apps/web/src/components/workspace-navigation.tsx"
EXPERIENCE_PATH = ROOT / "apps/web/src/components/decision-experience.tsx"
DECISION_PATH = ROOT / "apps/web/src/components/decision-feed.tsx"
JOURNAL_PATH = ROOT / "apps/web/src/components/outcome-journal-panel.tsx"
ALERT_PATH = ROOT / "apps/web/src/components/alert-inbox.tsx"
WATCHLIST_PATH = ROOT / "apps/web/src/components/watchlist-panel.tsx"
STYLES_PATH = ROOT / "apps/web/src/app/globals.css"
E2E_PATH = ROOT / "apps/web/tests/e2e/authenticated-shell.spec.ts"
WORKFLOW_PATH = ROOT / ".github/workflows/phase-three-ui-integration.yml"
P3_11_ACCEPTED_SHA = "306f2d1141bec65386c961e9fe36f9ab193fee3c"

EXPECTED_EXPERIENCES = {
    "decision_feed",
    "candidate_details",
    "risk_gate_explanation",
    "portfolio_candidate_impact",
    "human_decision_review",
    "alert_inbox",
    "watchlists",
    "outcome_journal",
}
EXPECTED_STATES = {
    "loading",
    "ready",
    "empty",
    "error",
    "degraded",
    "mutation_pending",
    "mutation_retry",
}


class PhaseThreeUiIntegrationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseThreeUiIntegrationError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def validate_prerequisite() -> None:
    prerequisite = load_json(P3_11_CONTRACT_PATH)
    require(prerequisite.get("decision_id") == "NEX-P3-11", "P3-11 decision drift")
    require(
        prerequisite.get("schema_version") == "nexora-phase-three-export-coverage-v1",
        "P3-11 schema drift",
    )
    transition = prerequisite.get("transition")
    require(isinstance(transition, dict), "P3-11 transition missing")
    require(
        transition.get("next_allowed_stage_after_ci_acceptance") == "NEX-P3-12",
        "P3-11 does not open P3-12",
    )
    require(transition.get("production_readiness_claimed") is False, "P3-11 production claim drift")


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("schema_version") == "nexora-phase-three-ui-integration-v1", "schema drift")
    require(contract.get("decision_id") == "NEX-P3-12", "stage ID drift")
    require(contract.get("status") == "candidate", "candidate status drift")
    prerequisite = contract.get("prerequisites")
    require(isinstance(prerequisite, dict), "prerequisites missing")
    require(prerequisite.get("p3_11_accepted_commit_sha") == P3_11_ACCEPTED_SHA, "P3-11 SHA drift")
    require(prerequisite.get("existing_authenticated_shell") is True, "authenticated shell removed")
    require(set(contract.get("experiences", [])) == EXPECTED_EXPERIENCES, "experience inventory drift")

    integration = contract.get("integration")
    require(isinstance(integration, dict), "integration policy missing")
    for key in (
        "single_owner_workspace",
        "selected_decision_context_shared",
        "selected_decision_opens_outcome_journal",
        "source_lineage_visible",
        "uncertainty_visible",
        "review_and_alert_history_visible",
        "safety_boundaries_visible",
    ):
        require(integration.get(key) is True, f"integration invariant disabled: {key}")
    for key in ("new_backend_route_required", "new_database_migration_required"):
        require(integration.get(key) is False, f"integration boundary widened: {key}")

    layout = contract.get("localization_and_layout")
    require(isinstance(layout, dict), "localization policy missing")
    require(layout.get("locales") == ["fa", "en"], "locale inventory drift")
    require(layout.get("persian_direction") == "rtl", "Persian direction drift")
    require(layout.get("english_direction") == "ltr", "English direction drift")
    require(layout.get("responsive_desktop_tablet_mobile") is True, "responsive layout disabled")
    require(layout.get("mobile_horizontal_page_overflow") is False, "mobile page overflow enabled")

    states = contract.get("state_model")
    require(isinstance(states, dict), "state model missing")
    require(set(states.get("states", [])) == EXPECTED_STATES, "state inventory drift")
    for key in (
        "failed_mutation_preserves_visible_evidence",
        "unchanged_retry_preserves_idempotency_key",
        "provider_degradation_is_explicit",
        "missing_evidence_is_not_fabricated",
        "session_expiry_uses_existing_shell_recovery",
    ):
        require(states.get(key) is True, f"state invariant disabled: {key}")

    accessibility = contract.get("accessibility")
    require(isinstance(accessibility, dict), "accessibility policy missing")
    require(accessibility.get("minimum_interactive_target_css_pixels") == 44, "target size drift")
    require(
        all(value is True for key, value in accessibility.items() if key != "minimum_interactive_target_css_pixels"),
        "accessibility invariant disabled",
    )

    browser = contract.get("browser_acceptance")
    require(isinstance(browser, dict), "browser acceptance missing")
    require(browser.get("real_provider_dependency") is False, "browser gate depends on a real provider")
    require(
        all(value is True for key, value in browser.items() if key != "real_provider_dependency"),
        "browser acceptance invariant disabled",
    )

    api = contract.get("api_boundary")
    require(isinstance(api, dict), "API boundary missing")
    for key in ("same_origin_api_only", "session_authentication_required", "owner_scope_derived_from_session"):
        require(api.get(key) is True, f"API invariant disabled: {key}")
    require(api.get("csrf_for_mutations") is True, "CSRF boundary disabled")
    require(api.get("browser_cache_mode") == "no-store", "browser caching enabled")
    for key in ("owner_id_accepted_from_browser", "direct_database_access", "direct_trd_bot_access"):
        require(api.get(key) is False, f"API boundary widened: {key}")

    security = contract.get("security_boundary")
    require(isinstance(security, dict) and not any(security.values()), "security boundary widened")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition missing")
    require(transition.get("next_allowed_stage_after_ci_acceptance") == "NEX-P3-13", "next stage drift")
    require(transition.get("phase_three_acceptance_deferred_to") == "NEX-P3-13", "acceptance moved")
    require(transition.get("production_readiness_claimed") is False, "production readiness claimed")
    require(
        transition.get("server_deployment_acceptance_satisfied") is False,
        "server acceptance incorrectly satisfied",
    )


def validate_runtime_markers() -> None:
    workspace = WORKSPACE_PATH.read_text(encoding="utf-8")
    navigation = NAVIGATION_PATH.read_text(encoding="utf-8")
    experience = EXPERIENCE_PATH.read_text(encoding="utf-8")
    decision = DECISION_PATH.read_text(encoding="utf-8")
    journal = JOURNAL_PATH.read_text(encoding="utf-8")
    alert = ALERT_PATH.read_text(encoding="utf-8")
    watchlist = WATCHLIST_PATH.read_text(encoding="utf-8")
    styles = STYLES_PATH.read_text(encoding="utf-8")
    english = load_json(ROOT / "apps/web/messages/en.json")
    persian = load_json(ROOT / "apps/web/messages/fa.json")

    require("<DecisionExperience" in workspace, "integrated Decision experience is not composed")
    require(
        'segment: "alerts"' in navigation and "<WatchlistPanel" in workspace,
        "Watchlists navigation through Alerts is not enabled",
    )
    for marker in (
        "export function DecisionExperience",
        "onDecisionChange={setActiveDecisionId}",
        "decisionId={activeDecisionId}",
        'aria-live="polite"',
        "<AlertInbox",
        "<WatchlistPanel",
    ):
        require(marker in experience, f"Decision integration marker missing: {marker}")
    for marker in (
        "decisionContextId",
        'event.key === "ArrowDown"',
        'event.key === "ArrowUp"',
        'event.key === "Home"',
        'event.key === "End"',
        "onKeyDown",
        "selectionSequence",
    ):
        require(marker in decision, f"keyboard Decision marker missing: {marker}")
    for marker in (
        "decisionId?: string",
        "integratedDecisionId",
        "loadSequence",
        "setDecisionInput(decisionId)",
        "void load(decisionId)",
    ):
        require(marker in journal, f"Journal integration marker missing: {marker}")
    for component, markers in (
        (decision, ("loading", "error", "emptyTitle", "providerDegraded")),
        (alert, ("loading", "error", "emptyTitle", "providerDegraded")),
        (watchlist, ("loading", "error", "emptyTitle", "operationError")),
        (journal, ("loading", "error", "emptyTitle", "operationError")),
    ):
        for marker in markers:
            require(marker in component, f"explicit UI state missing: {marker}")
    for marker in (
        ":focus-visible",
        "min-block-size: 2.75rem",
        "prefers-reduced-motion: reduce",
        ".decision-experience",
    ):
        require(marker in styles, f"accessibility style missing: {marker}")
    for locale, dictionary in (("en", english), ("fa", persian)):
        copy = dictionary.get("decisionExperience")
        require(isinstance(copy, dict), f"{locale} Decision integration dictionary missing")
        require(
            {"eyebrow", "title", "description", "activeDecision", "noActiveDecision"}.issubset(copy),
            f"{locale} Decision integration copy incomplete",
        )


def validate_browser_acceptance() -> None:
    browser = E2E_PATH.read_text(encoding="utf-8")
    for marker in (
        "Phase 3 Decision workflow is keyboard integrated and fixture backed",
        "Phase 3 surfaces degraded, empty and error states explicitly",
        "Loading the active decision projection…",
        'page.goto("/fa")',
        'page.goto("/en/decisions")',
        'candidateButton.press("End")',
        'secondDecision.press("Home")',
        'name: "Record immutable review"',
        'page.getByText("Accept · v1")',
        "document.documentElement.scrollWidth <= window.innerWidth",
        '"**/api/v1/decisions?**"',
        '"**/api/v1/alerts?**"',
        '"**/api/v1/watchlists?**"',
        '"**/api/v1/decisions/*/journal?**"',
    ):
        require(marker in browser, f"browser acceptance marker missing: {marker}")


def validate_workflow() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    for marker in (
        "python3 scripts/verify_phase_three_export_coverage.py",
        "python3 scripts/verify_phase_three_ui_integration.py",
        "python3 -m unittest discover -s tests -v",
        "uv run ruff format --check",
        "uv run ruff check",
        "uv run mypy",
        'uv run pytest -m "not integration" -q',
        "pnpm format:check",
        "pnpm lint",
        "pnpm typecheck",
        "pnpm test",
        "pnpm build",
        "playwright install --with-deps chromium",
        "pnpm --filter @nexora/web test:e2e",
    ):
        require(marker in workflow, f"P3-12 workflow marker missing: {marker}")


def verify() -> None:
    validate_prerequisite()
    validate_contract(load_contract())
    validate_runtime_markers()
    validate_browser_acceptance()
    validate_workflow()


def main() -> int:
    verify()
    print("NEX_P3_11_ACCEPTED_SHA=PASS")
    print("NEX_P3_12_UI_INTEGRATION=COMPLETE")
    print("NEX_P3_12_ACCESSIBILITY_AND_BROWSER_E2E=COMPLETE")
    print("NEX_P3_13=BLOCKED_PENDING_P3_12_CI_ACCEPTANCE")
    print("PRODUCTION_READINESS_CLAIMED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
