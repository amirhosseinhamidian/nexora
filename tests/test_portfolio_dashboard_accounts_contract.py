from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_portfolio_dashboard_accounts",
    ROOT / "scripts/verify_portfolio_dashboard_accounts.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PortfolioDashboardAccountsContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_p2_09_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p2_09()

    def test_candidate_contract_runtime_and_workflow_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_runtime_markers()
        MODULE.validate_workflow()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_owner_override_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["api_boundary"]["owner_id_accepted_from_browser"] = True
        with self.assertRaisesRegex(MODULE.PortfolioDashboardAccountsContractError, "owner_id"):
            MODULE.validate_contract(changed)

    def test_binary_float_financial_rendering_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["financial_presentation"]["binary_float_for_financial_amounts"] = True
        with self.assertRaisesRegex(MODULE.PortfolioDashboardAccountsContractError, "binary_float"):
            MODULE.validate_contract(changed)

    def test_unpriced_positions_cannot_be_implied_as_zero(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["financial_presentation"]["unpriced_positions_cannot_be_implied_as_zero"] = False
        with self.assertRaisesRegex(MODULE.PortfolioDashboardAccountsContractError, "unpriced_positions"):
            MODULE.validate_contract(changed)

    def test_external_account_reference_cannot_be_rendered(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["account_registry_boundary"]["external_account_reference_rendered"] = True
        with self.assertRaisesRegex(MODULE.PortfolioDashboardAccountsContractError, "external_account_reference"):
            MODULE.validate_contract(changed)

    def test_transaction_ui_cannot_enter_p2_10(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["transaction_ui_included"] = True
        with self.assertRaisesRegex(MODULE.PortfolioDashboardAccountsContractError, "transaction_ui"):
            MODULE.validate_contract(changed)

    def test_mobile_overflow_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["accessibility"]["mobile_horizontal_page_overflow"] = True
        with self.assertRaisesRegex(MODULE.PortfolioDashboardAccountsContractError, "overflow"):
            MODULE.validate_contract(changed)

    def test_only_p2_10_freeze_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P2-11"
        with self.assertRaisesRegex(MODULE.PortfolioDashboardAccountsContractError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
