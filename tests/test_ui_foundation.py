from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_ui_foundation",
    ROOT / "scripts/verify_ui_foundation.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P4-01 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class UiFoundationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_p4_00_prerequisite_is_valid(self) -> None:
        MODULE.validate_phase_four_prerequisite()

    def test_candidate_contract_and_runtime_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_runtime_markers()
        MODULE.validate_files_and_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_ui_package_boundary_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["package_boundary"]["package"] = "@nexora/web"
        with self.assertRaisesRegex(MODULE.UiFoundationContractError, "package boundary drift"):
            MODULE.validate_contract(changed)

    def test_required_component_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["component_inventory"]["overlays"].remove("confirmation_dialog")
        with self.assertRaisesRegex(MODULE.UiFoundationContractError, "component inventory drift"):
            MODULE.validate_contract(changed)

    def test_keyboard_requirement_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["accessibility_contract"]["keyboard_required"] = False
        with self.assertRaisesRegex(MODULE.UiFoundationContractError, "keyboard_required"):
            MODULE.validate_contract(changed)

    def test_dialog_focus_restoration_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["accessibility_contract"]["dialog_focus_restoration_required"] = False
        with self.assertRaisesRegex(MODULE.UiFoundationContractError, "dialog_focus_restoration"):
            MODULE.validate_contract(changed)

    def test_touch_target_minimum_cannot_be_weakened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["accessibility_contract"]["touch_target_minimum_css_pixels"] = 32
        with self.assertRaisesRegex(MODULE.UiFoundationContractError, "touch target"):
            MODULE.validate_contract(changed)

    def test_chart_equivalent_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["accessibility_contract"]["chart_text_or_table_equivalent_required"] = False
        with self.assertRaisesRegex(MODULE.UiFoundationContractError, "chart_text_or_table"):
            MODULE.validate_contract(changed)

    def test_rtl_ltr_requirement_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["direction_and_responsive_contract"]["rtl_ltr_required"] = False
        with self.assertRaisesRegex(MODULE.UiFoundationContractError, "responsive requirement"):
            MODULE.validate_contract(changed)

    def test_backend_changes_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["backend_domain_changes"] = True
        with self.assertRaisesRegex(MODULE.UiFoundationContractError, "forbidden security"):
            MODULE.validate_contract(changed)

    def test_production_readiness_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["acceptance"]["production_readiness_claimed"] = True
        with self.assertRaisesRegex(MODULE.UiFoundationContractError, "production_readiness"):
            MODULE.validate_contract(changed)

    def test_only_p4_01_freeze_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P4-02"
        with self.assertRaisesRegex(MODULE.UiFoundationContractError, "next stage drift"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
