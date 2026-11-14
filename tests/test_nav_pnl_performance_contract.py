from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_nav_pnl_performance", ROOT / "scripts/verify_nav_pnl_performance.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NavPnlPerformanceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze = MODULE.load_freeze_record()

    def test_frozen_p2_06_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p2_06()

    def test_candidate_contract_and_runtime_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_runtime_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_freeze_record_is_valid(self) -> None:
        MODULE.validate_freeze_record(self.freeze, self.contract)
        MODULE.validate_freeze_workflow()

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.NavPnlPerformanceContractError, "candidate SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_a_failed_check(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["checks"][0]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.NavPnlPerformanceContractError, "check evidence"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p2_08(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["next_allowed_stage"] = "NEX-P2-09"
        with self.assertRaisesRegex(MODULE.NavPnlPerformanceContractError, "next stage"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_incomplete_nav_cannot_be_silently_published(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["calculation_policy"]["nav_is_null_when_any_position_is_unpriced"] = False
        with self.assertRaisesRegex(MODULE.NavPnlPerformanceContractError, "nav_is_null"):
            MODULE.validate_contract(changed)

    def test_performance_cannot_become_unbounded(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["calculation_policy"]["performance_point_maximum"] = 1000
        with self.assertRaisesRegex(MODULE.NavPnlPerformanceContractError, "maximum"):
            MODULE.validate_contract(changed)

    def test_implicit_fx_inversion_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["valuation_resolution"]["implicit_fx_inversion"] = True
        with self.assertRaisesRegex(MODULE.NavPnlPerformanceContractError, "implicit_fx_inversion"):
            MODULE.validate_contract(changed)

    def test_paper_shadow_cannot_enter_p2_07(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["paper_shadow_projection_included"] = True
        with self.assertRaisesRegex(MODULE.NavPnlPerformanceContractError, "paper_shadow"):
            MODULE.validate_contract(changed)

    def test_freeze_transition_cannot_be_skipped(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P2-08"
        with self.assertRaisesRegex(MODULE.NavPnlPerformanceContractError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
