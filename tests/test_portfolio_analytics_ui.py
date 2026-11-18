from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_portfolio_analytics_ui", ROOT / "scripts/verify_portfolio_analytics_ui.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P4-05 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PortfolioAnalyticsUiContractTests(unittest.TestCase):
    def test_candidate_routes_and_frozen_prerequisite_are_valid(self) -> None:
        contract = MODULE.load_contract()
        MODULE.validate_prerequisite()
        MODULE.validate_contract(contract)
        MODULE.validate_runtime_markers(contract)

    def test_unavailable_returns_must_leave_chart_gaps(self) -> None:
        contract = MODULE.load_contract()
        contract["performance"]["chart_gap_for_unavailable_values"] = False
        with self.assertRaisesRegex(MODULE.PortfolioAnalyticsUiContractError, "chart_gap_for_unavailable_values"):
            MODULE.validate_contract(contract)

    def test_holdings_cannot_use_a_different_snapshot(self) -> None:
        contract = MODULE.load_contract()
        contract["holdings_source"] = "latest_holdings_projection"
        with self.assertRaisesRegex(MODULE.PortfolioAnalyticsUiContractError, "snapshot positions"):
            MODULE.validate_contract(contract)

    def test_p4_06_requires_freeze(self) -> None:
        contract = MODULE.load_contract()
        contract["transition"]["next_allowed_stage"] = "NEX-P4-06"
        with self.assertRaisesRegex(MODULE.PortfolioAnalyticsUiContractError, "stage transition drift"):
            MODULE.validate_contract(contract)

    def test_freeze_record_is_valid(self) -> None:
        MODULE.validate_freeze_record(MODULE.load_freeze_record(), MODULE.load_contract())

    def test_freeze_binds_ci_to_the_analytics_candidate(self) -> None:
        record = MODULE.load_freeze_record()
        record["github_actions"]["head_sha"] = MODULE.P4_04_FREEZE_SHA
        with self.assertRaisesRegex(MODULE.PortfolioAnalyticsUiContractError, "CI head SHA drift"):
            MODULE.validate_freeze_record(record, MODULE.load_contract())

    def test_freeze_requires_successful_web_and_browser_checks(self) -> None:
        record = MODULE.load_freeze_record()
        record["github_actions"]["jobs"]["portfolio-analytics-web"]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.PortfolioAnalyticsUiContractError, "CI job did not succeed"):
            MODULE.validate_freeze_record(record, MODULE.load_contract())

    def test_freeze_only_opens_p4_06(self) -> None:
        record = MODULE.load_freeze_record()
        record["next_allowed_stage"] = "NEX-P4-07"
        with self.assertRaisesRegex(MODULE.PortfolioAnalyticsUiContractError, "post-Freeze stage drift"):
            MODULE.validate_freeze_record(record, MODULE.load_contract())


if __name__ == "__main__":
    unittest.main()
