from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_valuation_evidence", ROOT / "scripts/verify_valuation_evidence.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ValuationEvidenceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_p2_05_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p2_05()

    def test_candidate_contract_and_runtime_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_runtime_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_silent_forward_fill_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["evidence_invariants"]["no_silent_forward_fill"] = False
        with self.assertRaisesRegex(MODULE.ValuationEvidenceContractError, "no_silent_forward_fill"):
            MODULE.validate_contract(changed)

    def test_nav_and_pnl_cannot_enter_p2_06(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["nav_included"] = True
        with self.assertRaisesRegex(MODULE.ValuationEvidenceContractError, "nav_included"):
            MODULE.validate_contract(changed)

    def test_freeze_transition_cannot_be_skipped(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P2-07"
        with self.assertRaisesRegex(MODULE.ValuationEvidenceContractError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
