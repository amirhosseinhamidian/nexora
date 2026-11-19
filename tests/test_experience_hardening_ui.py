from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_experience_hardening_ui", ROOT / "scripts/verify_experience_hardening_ui.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P4-10 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExperienceHardeningUiContractTests(unittest.TestCase):
    def test_candidate_and_frozen_prerequisite_are_valid(self) -> None:
        contract = MODULE.load_contract()
        MODULE.validate_prerequisite()
        MODULE.validate_contract(contract)
        MODULE.validate_runtime_markers(contract)

    def test_locale_copy_has_matching_labels(self) -> None:
        MODULE.validate_copy(
            MODULE.load_contract(ROOT / "apps/web/messages/en.json"),
            MODULE.load_contract(ROOT / "apps/web/messages/fa.json"),
        )

    def test_both_palettes_pass_and_low_contrast_is_rejected(self) -> None:
        contract = MODULE.load_contract()
        stylesheet = MODULE.TOKENS_PATH.read_text(encoding="utf-8")
        MODULE.validate_contrast(contract, stylesheet)
        invalid = stylesheet.replace("--nx-warning: #885100;", "--nx-warning: #fff5dc;")
        with self.assertRaisesRegex(MODULE.ExperienceHardeningUiContractError, "warning/warning-soft contrast"):
            MODULE.validate_contrast(contract, invalid)
