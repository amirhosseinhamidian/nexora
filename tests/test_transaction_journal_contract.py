from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_transaction_journal",
    ROOT / "scripts/verify_transaction_journal.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P2-03 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TransactionJournalContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_p2_02_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p2_02()

    def test_candidate_contract_and_runtime_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_runtime_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_in_place_edit_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["correction_policy"]["in_place_edit"] = True
        with self.assertRaisesRegex(MODULE.TransactionJournalContractError, "in_place_edit"):
            MODULE.validate_contract(changed)

    def test_database_immutability_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["journal_invariants"]["database_update_delete_rejected"] = False
        with self.assertRaisesRegex(MODULE.TransactionJournalContractError, "database_update_delete_rejected"):
            MODULE.validate_contract(changed)

    def test_balance_scope_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["journal_invariants"]["balance_scope"] = "portfolio_value"
        with self.assertRaisesRegex(MODULE.TransactionJournalContractError, "balance policy"):
            MODULE.validate_contract(changed)

    def test_binary_float_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["journal_invariants"]["binary_float_forbidden"] = False
        with self.assertRaisesRegex(MODULE.TransactionJournalContractError, "binary_float_forbidden"):
            MODULE.validate_contract(changed)

    def test_source_lineage_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["journal_invariants"]["source_lineage_required"] = False
        with self.assertRaisesRegex(MODULE.TransactionJournalContractError, "source_lineage_required"):
            MODULE.validate_contract(changed)

    def test_owner_override_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime_api"]["owner_id_accepted_from_request"] = True
        with self.assertRaisesRegex(MODULE.TransactionJournalContractError, "owner override"):
            MODULE.validate_contract(changed)

    def test_update_operation_cannot_be_exposed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime_api"]["update_operation_exposed"] = True
        with self.assertRaisesRegex(MODULE.TransactionJournalContractError, "update API"):
            MODULE.validate_contract(changed)

    def test_holdings_cannot_enter_p2_03(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["holdings_projection_included"] = True
        with self.assertRaisesRegex(MODULE.TransactionJournalContractError, "holdings_projection"):
            MODULE.validate_contract(changed)

    def test_live_orders_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_orders"] = True
        with self.assertRaisesRegex(MODULE.TransactionJournalContractError, "live_orders"):
            MODULE.validate_contract(changed)

    def test_p2_04_cannot_open_before_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P2-04"
        with self.assertRaisesRegex(MODULE.TransactionJournalContractError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
