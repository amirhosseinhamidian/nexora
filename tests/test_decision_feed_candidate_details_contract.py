from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_decision_feed_candidate_details",
    ROOT / "scripts/verify_decision_feed_candidate_details.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-04 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DecisionFeedCandidateDetailsContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_candidate_prerequisite_and_implementation_are_valid(self) -> None:
        MODULE.validate_prerequisite()
        MODULE.validate_contract(self.contract)
        MODULE.validate_implementation()

    def test_staging_generation_cannot_be_exposed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["api"]["staging_generation_visible"] = True
        with self.assertRaisesRegex(MODULE.DecisionFeedContractError, "staging"):
            MODULE.validate_contract(changed)

    def test_invalid_evidence_cannot_be_returned(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["api"]["invalid_projection_action"] = "return_partial"
        with self.assertRaisesRegex(MODULE.DecisionFeedContractError, "fail-closed"):
            MODULE.validate_contract(changed)

    def test_page_bound_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["api"]["maximum_page_size"] = None
        with self.assertRaisesRegex(MODULE.DecisionFeedContractError, "page bound"):
            MODULE.validate_contract(changed)

    def test_security_boundary_cannot_add_execution(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.DecisionFeedContractError, "security"):
            MODULE.validate_contract(changed)

    def test_p3_05_cannot_open_before_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P3-05"
        with self.assertRaisesRegex(MODULE.DecisionFeedContractError, "bypassed"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
