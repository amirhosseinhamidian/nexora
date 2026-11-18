from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_first_run_onboarding", ROOT / "scripts/verify_first_run_onboarding.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P4-03 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FirstRunOnboardingContractTests(unittest.TestCase):
    def test_candidate_and_frozen_prerequisite_are_valid(self) -> None:
        contract = MODULE.load_contract()
        MODULE.validate_prerequisite()
        MODULE.validate_contract(contract)
        MODULE.validate_runtime_markers(contract)

    def test_confirmation_cannot_be_removed(self) -> None:
        contract = MODULE.load_contract()
        contract["confirmation_required_before_writes"] = False
        with self.assertRaisesRegex(MODULE.FirstRunOnboardingContractError, "confirmation required"):
            MODULE.validate_contract(contract)

    def test_next_stage_requires_freeze(self) -> None:
        contract = MODULE.load_contract()
        contract["transition"]["next_allowed_stage"] = "NEX-P4-04"
        with self.assertRaisesRegex(MODULE.FirstRunOnboardingContractError, "stage transition drift"):
            MODULE.validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
