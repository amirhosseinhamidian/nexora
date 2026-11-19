from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_decision_intelligence_ui", ROOT / "scripts/verify_decision_intelligence_ui.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P4-07 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DecisionIntelligenceUiContractTests(unittest.TestCase):
    def test_candidate_routes_and_frozen_prerequisite_are_valid(self) -> None:
        contract = MODULE.load_contract()
        MODULE.validate_prerequisite()
        MODULE.validate_contract(contract)
        MODULE.validate_runtime_markers(contract)

    def test_execution_authority_is_rejected(self) -> None:
        contract = MODULE.load_contract()
        contract["boundary"]["execution_authorization"] = True
        with self.assertRaisesRegex(MODULE.DecisionIntelligenceUiContractError, "execution authorization"):
            MODULE.validate_contract(contract)
