from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_transactions_holdings_reconciliation_ui",
    ROOT / "scripts/verify_transactions_holdings_reconciliation_ui.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TransactionsHoldingsReconciliationUiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze = MODULE.load_freeze_record()

    def test_frozen_p2_10_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p2_10()

    def test_candidate_contract_runtime_and_workflow_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_runtime_markers()
        MODULE.validate_workflow()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_freeze_record_is_valid(self) -> None:
        MODULE.validate_freeze_record(self.freeze, self.contract)
        MODULE.validate_workflow()

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(
            MODULE.TransactionsHoldingsReconciliationUiContractError,
            "candidate SHA",
        ):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_a_failed_browser_job(self) -> None:
        changed = copy.deepcopy(self.freeze)
        browser = next(
            item
            for item in changed["checks"]
            if item["run_id"] == MODULE.P2_11_WORKFLOW_RUN_ID and item["name"] == "browser"
        )
        browser["conclusion"] = "failure"
        with self.assertRaisesRegex(
            MODULE.TransactionsHoldingsReconciliationUiContractError,
            "check evidence",
        ):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p2_12(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["next_allowed_stage"] = "NEX-P2-13"
        with self.assertRaisesRegex(
            MODULE.TransactionsHoldingsReconciliationUiContractError,
            "next stage",
        ):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_owner_override_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["api_boundary"]["owner_id_accepted_from_browser"] = True
        with self.assertRaisesRegex(MODULE.TransactionsHoldingsReconciliationUiContractError, "owner_id"):
            MODULE.validate_contract(changed)

    def test_binary_float_financial_rendering_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["journal_presentation"]["binary_float_for_financial_amounts"] = True
        with self.assertRaisesRegex(MODULE.TransactionsHoldingsReconciliationUiContractError, "binary_float"):
            MODULE.validate_contract(changed)

    def test_partial_import_publication_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["import_workflow"]["partial_publication"] = True
        with self.assertRaisesRegex(MODULE.TransactionsHoldingsReconciliationUiContractError, "partial_publication"):
            MODULE.validate_contract(changed)

    def test_automatic_journal_correction_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["reconciliation_workflow"]["automatic_journal_correction"] = True
        with self.assertRaisesRegex(
            MODULE.TransactionsHoldingsReconciliationUiContractError,
            "automatic_journal_correction",
        ):
            MODULE.validate_contract(changed)

    def test_recent_reauthentication_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["api_boundary"]["recent_reauthentication_for_publication_and_decisions"] = False
        with self.assertRaisesRegex(
            MODULE.TransactionsHoldingsReconciliationUiContractError,
            "recent_reauthentication",
        ):
            MODULE.validate_contract(changed)

    def test_projection_cannot_be_presented_as_journal_source_of_truth(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["holdings_and_lots"]["derived_projection_presented_as_source_of_truth"] = True
        with self.assertRaisesRegex(MODULE.TransactionsHoldingsReconciliationUiContractError, "source of truth"):
            MODULE.validate_contract(changed)

    def test_only_p2_11_freeze_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P2-12"
        with self.assertRaisesRegex(MODULE.TransactionsHoldingsReconciliationUiContractError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
