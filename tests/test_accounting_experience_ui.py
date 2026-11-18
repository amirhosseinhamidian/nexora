from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_accounting_experience_ui", ROOT / "scripts/verify_accounting_experience_ui.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P4-06 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AccountingExperienceUiContractTests(unittest.TestCase):
    def test_candidate_routes_and_frozen_prerequisite_are_valid(self) -> None:
        contract = MODULE.load_contract()
        MODULE.validate_prerequisite()
        MODULE.validate_contract(contract)
        MODULE.validate_runtime_markers(contract)

    def test_publication_and_reconciliation_both_require_recent_passkey(self) -> None:
        contract = MODULE.load_contract()
        contract["safety"]["recent_passkey_required"] = ["publication"]
        with self.assertRaisesRegex(MODULE.AccountingExperienceUiContractError, "recent passkey"):
            MODULE.validate_contract(contract)

    def test_reconciliation_requires_expected_row_version(self) -> None:
        contract = MODULE.load_contract()
        contract["safety"]["reconciliation_uses_expected_row_version"] = False
        with self.assertRaisesRegex(MODULE.AccountingExperienceUiContractError, "expected row version"):
            MODULE.validate_contract(contract)
