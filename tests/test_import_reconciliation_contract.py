from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_import_reconciliation",
    ROOT / "scripts/verify_import_reconciliation.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P2-04 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ImportReconciliationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_p2_03_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p2_03()

    def test_candidate_contract_and_runtime_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_runtime_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_partial_publish_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["import_invariants"]["partial_publish_forbidden"] = False
        with self.assertRaisesRegex(MODULE.ImportReconciliationContractError, "partial_publish"):
            MODULE.validate_contract(changed)

    def test_dry_run_cannot_be_skipped(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["import_invariants"]["dry_run_required"] = False
        with self.assertRaisesRegex(MODULE.ImportReconciliationContractError, "dry_run"):
            MODULE.validate_contract(changed)

    def test_automatic_journal_correction_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["reconciliation_policy"]["automatic_journal_correction"] = True
        with self.assertRaisesRegex(MODULE.ImportReconciliationContractError, "automatic_journal_correction"):
            MODULE.validate_contract(changed)

    def test_holdings_cannot_enter_p2_04(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["holdings_projection_included"] = True
        with self.assertRaisesRegex(MODULE.ImportReconciliationContractError, "holdings_projection"):
            MODULE.validate_contract(changed)

    def test_owner_override_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime_api"]["owner_id_accepted_from_request"] = True
        with self.assertRaisesRegex(MODULE.ImportReconciliationContractError, "owner override"):
            MODULE.validate_contract(changed)

    def test_live_orders_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_orders"] = True
        with self.assertRaisesRegex(MODULE.ImportReconciliationContractError, "live_orders"):
            MODULE.validate_contract(changed)

    def test_p2_05_cannot_open_before_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P2-05"
        with self.assertRaisesRegex(MODULE.ImportReconciliationContractError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
