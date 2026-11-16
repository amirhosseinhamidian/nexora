from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_human_decision_review",
    ROOT / "scripts/verify_human_decision_review.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-07 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HumanDecisionReviewContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_prerequisite_contract_and_implementation_are_valid(self) -> None:
        MODULE.validate_prerequisite()
        MODULE.validate_contract(self.contract)
        MODULE.validate_implementation()

    def test_review_action_set_cannot_expand(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["review_actions"].append("execute")
        with self.assertRaisesRegex(MODULE.HumanDecisionReviewContractError, "actions"):
            MODULE.validate_contract(changed)

    def test_append_only_policy_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["persistence"]["append_only_reviews"] = False
        with self.assertRaisesRegex(MODULE.HumanDecisionReviewContractError, "persistence"):
            MODULE.validate_contract(changed)

    def test_local_review_must_remain_source_of_truth(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["provider_feedback"]["local_review_is_source_of_truth"] = False
        with self.assertRaisesRegex(MODULE.HumanDecisionReviewContractError, "source_of_truth"):
            MODULE.validate_contract(changed)

    def test_review_cannot_authorize_execution(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["review_authorizes_execution"] = True
        with self.assertRaisesRegex(MODULE.HumanDecisionReviewContractError, "security"):
            MODULE.validate_contract(changed)

    def test_p3_08_requires_p3_07_ci_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage_after_ci_acceptance"] = "NEX-P3-09"
        with self.assertRaisesRegex(MODULE.HumanDecisionReviewContractError, "next stage"):
            MODULE.validate_contract(changed)

    def test_nex_p3_03_remains_blocked(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["nex_p3_03_gate_opened"] = True
        with self.assertRaisesRegex(MODULE.HumanDecisionReviewContractError, "prematurely"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
