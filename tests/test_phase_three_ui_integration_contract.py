from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_phase_three_ui_integration",
    ROOT / "scripts/verify_phase_three_ui_integration.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-12 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhaseThreeUiIntegrationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_prerequisite_contract_runtime_browser_and_workflow_are_valid(self) -> None:
        MODULE.validate_prerequisite()
        MODULE.validate_contract(self.contract)
        MODULE.validate_runtime_markers()
        MODULE.validate_browser_acceptance()
        MODULE.validate_workflow()

    def test_experience_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["experiences"].remove("outcome_journal")
        with self.assertRaisesRegex(MODULE.PhaseThreeUiIntegrationError, "experience inventory"):
            MODULE.validate_contract(changed)

    def test_selected_decision_must_open_the_journal(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["integration"]["selected_decision_opens_outcome_journal"] = False
        with self.assertRaisesRegex(MODULE.PhaseThreeUiIntegrationError, "selected_decision"):
            MODULE.validate_contract(changed)

    def test_keyboard_navigation_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["accessibility"]["keyboard_decision_navigation"] = False
        with self.assertRaisesRegex(MODULE.PhaseThreeUiIntegrationError, "accessibility"):
            MODULE.validate_contract(changed)

    def test_mobile_overflow_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["localization_and_layout"]["mobile_horizontal_page_overflow"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeUiIntegrationError, "overflow"):
            MODULE.validate_contract(changed)

    def test_real_provider_cannot_become_a_browser_dependency(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["browser_acceptance"]["real_provider_dependency"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeUiIntegrationError, "real provider"):
            MODULE.validate_contract(changed)

    def test_browser_owner_override_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["api_boundary"]["owner_id_accepted_from_browser"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeUiIntegrationError, "owner_id"):
            MODULE.validate_contract(changed)

    def test_execution_capability_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["creates_order_intent"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeUiIntegrationError, "security"):
            MODULE.validate_contract(changed)

    def test_next_stage_cannot_skip_phase_three_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage_after_ci_acceptance"] = "NEX-P4-00"
        with self.assertRaisesRegex(MODULE.PhaseThreeUiIntegrationError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
