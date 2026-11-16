from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_portfolio_candidate_impact",
    ROOT / "scripts/verify_portfolio_candidate_impact.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-06 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PortfolioCandidateImpactContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_prerequisite_contract_and_implementation_are_valid(self) -> None:
        MODULE.validate_prerequisite()
        MODULE.validate_contract(self.contract)
        MODULE.validate_implementation()

    def test_bounded_scenario_set_cannot_change(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["provider_analysis"]["required_scenario_shocks"].pop()
        with self.assertRaisesRegex(MODULE.PortfolioCandidateImpactContractError, "scenario"):
            MODULE.validate_contract(changed)

    def test_portfolio_check_set_cannot_be_reduced(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["provider_analysis"]["required_checks"].pop()
        with self.assertRaisesRegex(MODULE.PortfolioCandidateImpactContractError, "check set"):
            MODULE.validate_contract(changed)

    def test_risk_gate_checksum_cross_validation_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["provider_analysis"]["risk_gate_checksum_cross_validated"] = False
        with self.assertRaisesRegex(MODULE.PortfolioCandidateImpactContractError, "Risk Gate"):
            MODULE.validate_contract(changed)

    def test_nexora_cannot_recompute_provider_analysis(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["ownership_boundary"]["nexora_recomputes_portfolio_analysis"] = True
        with self.assertRaisesRegex(MODULE.PortfolioCandidateImpactContractError, "ownership"):
            MODULE.validate_contract(changed)

    def test_personal_asset_binding_cannot_open_without_a_versioned_map(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["personal_asset_mapping_added"] = True
        with self.assertRaisesRegex(MODULE.PortfolioCandidateImpactContractError, "scope"):
            MODULE.validate_contract(changed)

    def test_p3_07_requires_p3_06_ci_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage_after_ci_acceptance"] = "NEX-P3-08"
        with self.assertRaisesRegex(MODULE.PortfolioCandidateImpactContractError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
