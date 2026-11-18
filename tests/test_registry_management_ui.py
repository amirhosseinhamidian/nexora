from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_registry_management_ui", ROOT / "scripts/verify_registry_management_ui.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P4-04 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RegistryManagementUiContractTests(unittest.TestCase):
    def test_candidate_routes_and_frozen_prerequisite_are_valid(self) -> None:
        contract = MODULE.load_contract()
        MODULE.validate_prerequisite()
        MODULE.validate_contract(contract)
        MODULE.validate_runtime_markers(contract)

    def test_lifecycle_requires_confirmation_and_the_loaded_version(self) -> None:
        for safeguard in ("confirmation_required", "requires_expected_row_version"):
            with self.subTest(safeguard=safeguard):
                contract = MODULE.load_contract()
                contract["lifecycle"][safeguard] = False
                with self.assertRaisesRegex(MODULE.RegistryManagementUiContractError, "lifecycle safeguards drift"):
                    MODULE.validate_contract(contract)

    def test_uncontracted_rename_is_rejected(self) -> None:
        contract = MODULE.load_contract()
        contract["boundary"]["rename_or_general_update"] = True
        with self.assertRaisesRegex(MODULE.RegistryManagementUiContractError, "updates require a separate contract"):
            MODULE.validate_contract(contract)

    def test_p4_05_requires_freeze(self) -> None:
        contract = MODULE.load_contract()
        contract["transition"]["next_allowed_stage"] = "NEX-P4-05"
        with self.assertRaisesRegex(MODULE.RegistryManagementUiContractError, "stage transition drift"):
            MODULE.validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
