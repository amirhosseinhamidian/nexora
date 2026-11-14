from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_durable_decision_event_projection",
    ROOT / "scripts/verify_durable_decision_event_projection.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-03 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DurableDecisionEventProjectionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_candidate_and_frozen_prerequisite_are_valid(self) -> None:
        MODULE.validate_prerequisite()
        MODULE.validate_contract(self.contract)
        MODULE.validate_implementation()

    def test_partial_publication_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["persistence"]["partial_generation_publish_allowed"] = True
        with self.assertRaisesRegex(MODULE.DurableDecisionProjectionError, "partial"):
            MODULE.validate_contract(changed)

    def test_unknown_schema_cannot_be_applied(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["projection"]["unknown_schema_action"] = "apply"
        with self.assertRaisesRegex(MODULE.DurableDecisionProjectionError, "schema gate"):
            MODULE.validate_contract(changed)

    def test_quarantine_cannot_open_next_stage(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["full_resync"]["activation_requires_zero_quarantine"] = False
        with self.assertRaisesRegex(MODULE.DurableDecisionProjectionError, "resync invariant"):
            MODULE.validate_contract(changed)

    def test_event_resume_cannot_precede_activation(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["full_resync"]["event_resume_enqueued_only_after_activation"] = False
        with self.assertRaisesRegex(MODULE.DurableDecisionProjectionError, "resync invariant"):
            MODULE.validate_contract(changed)

    def test_security_boundary_cannot_add_live_orders(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.DurableDecisionProjectionError, "forbidden security"):
            MODULE.validate_contract(changed)

    def test_p3_04_cannot_open_before_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P3-04"
        with self.assertRaisesRegex(MODULE.DurableDecisionProjectionError, "bypasses acceptance"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
