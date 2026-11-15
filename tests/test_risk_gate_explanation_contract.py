from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_risk_gate_explanation",
    ROOT / "scripts/verify_risk_gate_explanation.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-05 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RiskGateExplanationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_prerequisite_contract_and_implementation_are_valid(self) -> None:
        MODULE.validate_prerequisite()
        MODULE.validate_contract(self.contract)
        MODULE.validate_implementation()

    def test_provider_reason_namespace_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["explanation"]["provider_reason_namespace"] = None
        with self.assertRaisesRegex(MODULE.RiskGateExplanationContractError, "namespace"):
            MODULE.validate_contract(changed)

    def test_missing_uncertainty_cannot_be_hidden(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["explanation"]["missing_uncertainty_action"] = "omit"
        with self.assertRaisesRegex(MODULE.RiskGateExplanationContractError, "uncertainty"):
            MODULE.validate_contract(changed)

    def test_provider_check_set_cannot_be_reduced(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["explanation"]["required_provider_checks"].pop()
        with self.assertRaisesRegex(MODULE.RiskGateExplanationContractError, "check set"):
            MODULE.validate_contract(changed)

    def test_nexora_cannot_recompute_the_risk_decision(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["ownership_boundary"]["nexora_recomputes_risk_gate"] = True
        with self.assertRaisesRegex(MODULE.RiskGateExplanationContractError, "ownership"):
            MODULE.validate_contract(changed)

    def test_position_sizing_cannot_open_in_p3_05(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["portfolio_impact_or_position_sizing_exposed"] = True
        with self.assertRaisesRegex(MODULE.RiskGateExplanationContractError, "scope"):
            MODULE.validate_contract(changed)

    def test_p3_06_cannot_open_before_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P3-06"
        with self.assertRaisesRegex(MODULE.RiskGateExplanationContractError, "bypassed"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
