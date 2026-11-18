#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-ui-foundation.json"
P4_00_FREEZE_PATH = ROOT / "artifacts/p4-00/phase-four-product-experience-roadmap-freeze.json"

CONTRACT_CHECKSUM = "dd1cd6090916334bcfc51614a4bf38d876b5117d07bb3555751dace42a22ec52"
P4_00_FREEZE_CANONICAL_CHECKSUM = "df373401cf0982b09708d0093d0492cdddf365c85195fbc2e1374293bc3a5584"
P4_00_CANDIDATE_SHA = "1fc09c0354876d1ced6eebd7fe8d29338a8c9e8d"
P4_00_FREEZE_SHA = "c880972eee63569d1509ac0ed58eceb84521d6a9"
P4_00_VERIFIER_FIX_SHA = "079efb63e7b57b32c9d1902da30b27f75edddbe0"
P4_00_SUCCESSFUL_RUN_ID = 44312235596

EXPECTED_COMPONENTS = {
    "button",
    "icon_button",
    "form_field",
    "field_error",
    "input",
    "textarea",
    "select",
    "checkbox",
    "radio",
    "switch",
    "search_input",
    "alert",
    "toast_region",
    "progress",
    "spinner",
    "skeleton",
    "empty_state",
    "error_state",
    "offline_state",
    "degraded_state",
    "modal",
    "confirmation_dialog",
    "drawer",
    "sheet",
    "tooltip",
    "popover",
    "dropdown_menu",
    "table",
    "responsive_record_list",
    "pagination",
    "tabs",
    "filter_bar",
    "stat_card",
    "chart_container",
    "chart_legend",
    "comparison_block",
}
EXPECTED_STATES = {
    "default",
    "hover",
    "focus_visible",
    "active",
    "disabled",
    "loading",
    "invalid",
}
EXPECTED_DATA_STATES = {"loading", "empty", "error", "offline", "degraded", "ready"}
FORBIDDEN_SECURITY_FLAGS = {
    "authentication_changes",
    "authorization_changes",
    "backend_domain_changes",
    "physical_delete_capability",
    "live_execution_capability",
    "financial_advice",
    "production_readiness_claimed",
}


class UiFoundationContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise UiFoundationContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_phase_four_prerequisite(path: Path = P4_00_FREEZE_PATH) -> None:
    record = _json(path)
    _require(canonical_checksum(record) == P4_00_FREEZE_CANONICAL_CHECKSUM, "P4-00 Freeze artifact drift")
    _require(record.get("decision_id") == "NEX-P4-00", "P4-00 decision drift")
    _require(record.get("candidate_commit_sha") == P4_00_CANDIDATE_SHA, "P4-00 candidate drift")
    _require(record.get("frozen") is True, "P4-00 is not frozen")
    _require(record.get("next_allowed_stage") == "NEX-P4-01", "P4-01 is not open")
    _require(record.get("production_readiness_claimed") is False, "P4-00 production claim")


def _component_inventory(contract: dict[str, Any]) -> set[str]:
    inventory = contract.get("component_inventory")
    _require(isinstance(inventory, dict), "component inventory must be an object")
    components: set[str] = set()
    for category, values in inventory.items():
        _require(isinstance(values, list) and values, f"component category is empty: {category}")
        components.update(values)
    return components


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-ui-foundation-v1", "invalid schema version")
    _require(contract.get("decision_id") == "NEX-P4-01", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-11-18", "invalid decision date")
    _require(contract.get("status") == "candidate", "P4-01 must remain a candidate")

    prerequisite = contract.get("phase_four_prerequisite")
    _require(isinstance(prerequisite, dict), "P4-00 prerequisite must be an object")
    _require(prerequisite.get("frozen") is True, "P4-00 prerequisite must be frozen")
    _require(prerequisite.get("accepted_candidate_commit_sha") == P4_00_CANDIDATE_SHA, "P4-00 candidate drift")
    _require(prerequisite.get("freeze_commit_sha") == P4_00_FREEZE_SHA, "P4-00 Freeze commit drift")
    _require(prerequisite.get("freeze_verifier_fix_sha") == P4_00_VERIFIER_FIX_SHA, "P4-00 verifier fix drift")
    _require(
        prerequisite.get("freeze_record_canonical_checksum") == P4_00_FREEZE_CANONICAL_CHECKSUM,
        "P4-00 Freeze checksum drift",
    )
    _require(prerequisite.get("successful_ci_run_id") == P4_00_SUCCESSFUL_RUN_ID, "P4-00 CI run drift")
    _require(
        prerequisite.get("successful_ci_run_url")
        == f"https://github.com/amirhosseinhamidian/nexora/actions/runs/{P4_00_SUCCESSFUL_RUN_ID}",
        "P4-00 CI run URL drift",
    )
    _require(prerequisite.get("next_allowed_stage") == "NEX-P4-01", "P4-01 prerequisite is not open")
    _require(prerequisite.get("production_readiness_claimed") is False, "P4-00 production claim")

    boundary = contract.get("package_boundary")
    _require(isinstance(boundary, dict), "package boundary must be an object")
    _require(boundary.get("package") == "@nexora/ui", "UI package boundary drift")
    _require(boundary.get("component_entrypoint") == "@nexora/ui/primitives", "component entrypoint drift")
    for flag in ("application_imports_global_styles_once", "feature_pages_must_not_duplicate_primitives"):
        _require(boundary.get(flag) is True, f"package boundary requirement disabled: {flag}")
    for flag in ("domain_logic_allowed", "network_access_allowed", "runtime_financial_data_allowed"):
        _require(boundary.get(flag) is False, f"package boundary capability enabled: {flag}")

    tokens = contract.get("token_contract")
    _require(isinstance(tokens, dict), "token contract must be an object")
    _require(tokens.get("control_sizes") == ["sm", "md", "lg"], "control size drift")
    for flag in (
        "logical_properties_required",
        "light_dark_themes_required",
        "persian_english_fonts_required",
        "spacing_scale_required",
        "radius_scale_required",
        "reduced_motion_required",
    ):
        _require(tokens.get(flag) is True, f"token requirement disabled: {flag}")

    _require(_component_inventory(contract) == EXPECTED_COMPONENTS, "component inventory drift")

    states = contract.get("state_contract")
    _require(isinstance(states, dict), "state contract must be an object")
    _require(set(states.get("interactive_states", [])) == EXPECTED_STATES, "interactive state drift")
    _require(set(states.get("data_states", [])) == EXPECTED_DATA_STATES, "data state drift")
    _require(states.get("destructive_actions_use_danger_tone") is True, "danger tone disabled")
    _require(
        states.get("loading_actions_prevent_duplicate_submission") is True, "duplicate submission protection disabled"
    )

    accessibility = contract.get("accessibility_contract")
    _require(isinstance(accessibility, dict), "accessibility contract must be an object")
    for key, value in accessibility.items():
        if key == "touch_target_minimum_css_pixels":
            _require(isinstance(value, int) and value >= 36, "touch target minimum weakened")
        else:
            _require(value is True, f"accessibility requirement disabled: {key}")

    responsive = contract.get("direction_and_responsive_contract")
    _require(isinstance(responsive, dict), "responsive contract must be an object")
    _require(all(value is True for value in responsive.values()), "responsive requirement disabled")

    content = contract.get("content_contract")
    _require(isinstance(content, dict), "content contract must be an object")
    _require(all(value is True for value in content.values()), "content requirement disabled")

    acceptance = contract.get("acceptance")
    _require(isinstance(acceptance, dict), "acceptance must be an object")
    for key, value in acceptance.items():
        _require(value is (key != "production_readiness_claimed"), f"acceptance drift: {key}")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security boundary must be an object")
    _require(set(security) == FORBIDDEN_SECURITY_FLAGS, "security flag inventory drift")
    _require(not any(security.values()), "P4-01 changed a forbidden security capability")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("next_allowed_stage") == "NEX-P4-01-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P4-02", "post-Freeze stage drift")
    _require(transition.get("freeze_before_next_stage") is True, "P4-01 Freeze gate removed")


def validate_runtime_markers() -> None:
    package = _json(ROOT / "packages/ui/package.json")
    exports = package.get("exports")
    _require(isinstance(exports, dict), "UI package exports must be an object")
    _require(exports.get("./primitives") == "./src/primitives.tsx", "primitive export missing")
    _require(exports.get("./primitives.css") == "./src/primitives.css", "primitive style export missing")

    root_package = _json(ROOT / "package.json")
    scripts = root_package.get("scripts")
    _require(isinstance(scripts, dict), "root scripts must be an object")
    for name in ("format", "format:check", "lint"):
        _require("packages/ui" in scripts.get(name, ""), f"root {name} does not cover the UI package")

    source = (ROOT / "packages/ui/src/primitives.tsx").read_text(encoding="utf-8")
    css = (ROOT / "packages/ui/src/primitives.css").read_text(encoding="utf-8")
    tokens = (ROOT / "packages/ui/src/tokens.css").read_text(encoding="utf-8")
    layout = (ROOT / "apps/web/src/app/[locale]/layout.tsx").read_text(encoding="utf-8")

    exported = {
        name
        for name in (
            "Button",
            "IconButton",
            "FormField",
            "FieldError",
            "Input",
            "SearchInput",
            "Textarea",
            "Select",
            "Checkbox",
            "Radio",
            "Switch",
            "Alert",
            "ToastRegion",
            "Progress",
            "Spinner",
            "Skeleton",
            "EmptyState",
            "ErrorState",
            "OfflineState",
            "DegradedState",
            "Modal",
            "ConfirmationDialog",
            "Drawer",
            "Sheet",
            "Tooltip",
            "Popover",
            "DropdownMenu",
            "Table",
            "ResponsiveRecordList",
            "Pagination",
            "Tabs",
            "FilterBar",
            "StatCard",
            "ChartContainer",
            "ChartLegend",
            "ComparisonBlock",
        )
        if f"export function {name}" in source
    }
    _require(len(exported) == len(EXPECTED_COMPONENTS), "runtime component export missing")
    for marker in (
        'event.key === "Escape"',
        'event.key !== "Tab"',
        'document.body.style.overflow = "hidden"',
        "previouslyFocused?.focus()",
        'aria-modal="true"',
        'role="progressbar"',
        'aria-live="polite"',
        'aria-hidden="true" className="nx-chart__visual"',
    ):
        _require(marker in source, f"accessibility runtime marker missing: {marker}")
    for marker in (
        "inline-size",
        "block-size",
        "inset-inline",
        '[dir="rtl"]',
        "prefers-reduced-motion: reduce",
        ".nx-table--responsive",
        "overflow-x: auto",
    ):
        _require(marker in css, f"responsive style marker missing: {marker}")
    for marker in ("--nx-control-sm", "--nx-success-soft", '[data-theme="dark"]'):
        _require(marker in tokens, f"design token missing: {marker}")
    _require('import "@nexora/ui/primitives.css"' in layout, "shared primitive styles are not loaded")


def validate_files_and_markers() -> None:
    expected = {
        "README.md": "NEX_P4_01_UI_FOUNDATION_CANDIDATE=PASS",
        "docs/v0.1/48-ui-foundation-and-micro-components.md": "# NEX-P4-01",
        ".github/workflows/ui-foundation.yml": "name: UI foundation and micro components",
        "apps/web/src/components/ui-primitives.test.tsx": 'describe("shared UI primitives"',
    }
    for relative, marker in expected.items():
        content = (ROOT / relative).read_text(encoding="utf-8")
        _require(marker in content, f"{relative} is missing the P4-01 marker")


def main() -> int:
    validate_phase_four_prerequisite()
    contract = load_contract()
    validate_contract(contract)
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P4-01 contract checksum drift")
    validate_runtime_markers()
    validate_files_and_markers()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P4_00_FREEZE_PREREQUISITE=PASS")
    print("NEX_P4_01_UI_FOUNDATION_CANDIDATE=PASS")
    print("NEX_P4_01_FREEZE=PENDING_SAME_SHA_CI")
    print("NEX_P4_02=BLOCKED_PENDING_P4_01_FREEZE")
    print("PRODUCTION_READINESS_CLAIMED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
