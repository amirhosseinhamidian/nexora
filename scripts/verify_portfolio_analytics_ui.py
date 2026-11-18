#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-portfolio-analytics-ui.json"
P4_04_FREEZE_PATH = ROOT / "artifacts/p4-04/registry-management-ui-freeze.json"
FREEZE_PATH = ROOT / "artifacts/p4-05/portfolio-analytics-ui-freeze.json"
CONTRACT_CHECKSUM = "f1ed43062b0f2e5bb8ad46bf37068c344311c18fd9630fbfeaa9f75d8acd5ad4"
FREEZE_CHECKSUM = "2ea7cb5dfda189daa7241a164005dd68d8e2f1f6a2056089239e6d61a0792c1f"
P4_04_FREEZE_CHECKSUM = "fde080e0d1ac0a260ad1214340c46fee9c9fd7f9453122e485ce36d662394ef9"
P4_04_FREEZE_SHA = "ea7025148103004a6441377077b14aee1014f328"
P4_04_FREEZE_CI_RUN_ID = 44395721270
P4_05_CANDIDATE_SHA = "17d0940aed4057d46f7f1af99e804b7c6d98db07"


class PortfolioAnalyticsUiContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PortfolioAnalyticsUiContractError(message)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path.name} must contain an object")
    return value


def canonical_checksum(document: dict[str, Any]) -> str:
    payload = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return load_contract(path)


def validate_prerequisite() -> None:
    freeze = load_contract(P4_04_FREEZE_PATH)
    _require(canonical_checksum(freeze) == P4_04_FREEZE_CHECKSUM, "P4-04 Freeze checksum drift")
    _require(freeze.get("frozen") is True, "P4-04 is not frozen")
    _require(freeze.get("next_allowed_stage") == "NEX-P4-05", "P4-05 is not open")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-portfolio-analytics-ui-v1", "schema drift")
    _require(contract.get("decision_id") == "NEX-P4-05", "decision drift")
    _require(contract.get("status") == "candidate", "status drift")
    _require(
        contract.get("p4_04_prerequisite")
        == {
            "freeze_commit_sha": P4_04_FREEZE_SHA,
            "freeze_record_path": P4_04_FREEZE_PATH.relative_to(ROOT).as_posix(),
            "freeze_record_checksum": P4_04_FREEZE_CHECKSUM,
            "successful_ci_run_id": P4_04_FREEZE_CI_RUN_ID,
        },
        "P4-04 prerequisite drift",
    )
    _require(contract.get("holdings_source") == "analytics.positions", "holdings must use the snapshot positions")
    performance = contract.get("performance", {})
    for key in ("chart_gap_for_unavailable_values", "stale_evidence_visible", "text_or_table_equivalent_required"):
        _require(performance.get(key) is True, f"performance requires {key}")
    _require(
        contract.get("boundary", {}).get("invented_returns_or_values") is False,
        "analytics cannot invent returns or values",
    )
    _require(
        contract.get("transition") == {"next_allowed_stage": "NEX-P4-05-FREEZE", "post_freeze_stage": "NEX-P4-06"},
        "stage transition drift",
    )
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "P4-05 contract checksum drift")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-portfolio-analytics-ui-freeze-v1", "invalid Freeze schema")
    _require(record.get("decision_id") == contract.get("decision_id") == "NEX-P4-05", "Freeze decision drift")
    _require(record.get("candidate_commit_sha") == P4_05_CANDIDATE_SHA, "P4-05 candidate SHA drift")
    _require(record.get("candidate_predecessor_sha") == P4_04_FREEZE_SHA, "candidate is not based on the P4-04 Freeze")
    _require(record.get("p4_04_freeze_canonical_checksum") == P4_04_FREEZE_CHECKSUM, "P4-04 Freeze drift")
    _require(
        record.get("portfolio_analytics_ui_contract")
        == {"path": CONTRACT_PATH.relative_to(ROOT).as_posix(), "checksum": canonical_checksum(contract)},
        "Freeze contract evidence drift",
    )

    workflow = record.get("github_actions")
    _require(isinstance(workflow, dict), "GitHub Actions evidence must be an object")
    _require(workflow.get("workflow_path") == ".github/workflows/portfolio-analytics-ui.yml", "CI workflow drift")
    _require(workflow.get("head_sha") == P4_05_CANDIDATE_SHA, "CI head SHA drift")
    _require(workflow.get("conclusion") == "success", "CI did not succeed")
    jobs = workflow.get("jobs")
    _require(isinstance(jobs, dict), "CI jobs must be an object")
    _require(set(jobs) == {"portfolio-analytics-contract", "portfolio-analytics-web"}, "CI job inventory drift")
    for name, job in jobs.items():
        _require(isinstance(job, dict) and job.get("conclusion") == "success", f"CI job did not succeed: {name}")

    _require(record.get("frozen") is True, "P4-05 is not frozen")
    _require(record.get("next_allowed_stage") == contract["transition"]["post_freeze_stage"], "post-Freeze stage drift")
    _require(record.get("production_readiness_claimed") is False, "Freeze production claim")
    _require(canonical_checksum(record) == FREEZE_CHECKSUM, "P4-05 Freeze checksum drift")


def validate_runtime_markers(contract: dict[str, Any]) -> None:
    web = ROOT / "apps/web/src"
    workspace = (web / "components/workspace-view.tsx").read_text(encoding="utf-8")
    dashboard = (web / "components/portfolio-dashboard.tsx").read_text(encoding="utf-8")
    holdings = (web / "components/portfolio-holdings.tsx").read_text(encoding="utf-8")
    performance = (web / "components/portfolio-performance.tsx").read_text(encoding="utf-8")
    calculation = (web / "lib/portfolio-analytics.ts").read_text(encoding="utf-8")
    api = load_contract(ROOT / "contracts/runtime/v1/openapi.json")["paths"]

    route_sections = {"overview": "overview", "portfolios/{portfolio_id}": "portfolioDetail"}
    for route in contract["routes"]:
        segment = route.removeprefix("/{locale}/")
        page = web / f"app/[locale]/(workspace)/{segment.replace('{portfolio_id}', '[portfolioId]')}/page.tsx"
        _require(f'section="{route_sections[segment]}"' in page.read_text(encoding="utf-8"), f"route drift: {route}")
    _require("<PortfolioDashboard" in workspace, "portfolio dashboard is not routed through the workspace")
    for path, operation in contract["read_operations"].items():
        _require(api.get(path, {}).get("get", {}).get("operationId") == operation, f"read operation drift: {path}")
    for period, window in contract["performance"]["as_of_anchored_windows"].items():
        marker = f"{period}: {{ days: {window['days']}, sampleCount: {window['points']} }}"
        _require(marker in calculation, f"performance sampling window drift: {period}")
    for marker in ("positions={details.analytics.positions}", "<PortfolioHoldings", "<PortfolioPerformance"):
        _require(marker in dashboard, f"analytics workspace marker missing: {marker}")
    _require("<Table" in holdings and "formatExactQuantity" in holdings, "holdings table or decimal precision drift")
    for marker in (
        "performancePath(portfolioId, asOf, period)",
        "<ComparisonBlock",
        "<ChartContainer",
        "<PerformanceTable",
        "if (!sample || !previous) return null",
    ):
        _require(marker in performance, f"performance view marker missing: {marker}")
    for source in (dashboard, holdings, performance, calculation):
        _require('method: "POST"' not in source, "portfolio analytics must remain read-only")


def main() -> int:
    contract = load_contract()
    validate_prerequisite()
    validate_contract(contract)
    validate_runtime_markers(contract)
    validate_freeze_record(load_freeze_record(), contract)
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={CONTRACT_CHECKSUM}")
    print("NEX_P4_04_PREREQUISITE=PASS")
    print("NEX_P4_05_PORTFOLIO_ANALYTICS_UI_CANDIDATE=PASS")
    print(f"candidate_commit_sha={P4_05_CANDIDATE_SHA}")
    print(f"freeze_checksum={FREEZE_CHECKSUM}")
    print("NEX_P4_05_FREEZE=PASS")
    print("NEX_P4_06=OPEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
