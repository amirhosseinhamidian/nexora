from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_phase_one_final_acceptance",
    ROOT / "scripts/verify_phase_one_final_acceptance.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load Phase 1 final acceptance verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhaseOneFinalAcceptanceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_p1_12_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p1_12()

    def test_candidate_contract_and_tooling_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files_and_runtime_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_prerequisite_cannot_be_rebound(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["p1_12_prerequisite"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PhaseOneFinalAcceptanceContractError, "commit drift"):
            MODULE.validate_contract(changed)

    def test_evidence_freshness_cannot_be_relaxed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["evidence"]["maximum_age_days"] = 30
        with self.assertRaisesRegex(MODULE.PhaseOneFinalAcceptanceContractError, "freshness"):
            MODULE.validate_contract(changed)

    def test_destructive_database_cannot_target_development(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["destructive_database_boundary"]["required_database_name"] = "nexora"
        with self.assertRaisesRegex(MODULE.PhaseOneFinalAcceptanceContractError, "database drift"):
            MODULE.validate_contract(changed)

    def test_restore_rto_cannot_be_relaxed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["operations_acceptance"]["restore_rto_hours"] = 24
        with self.assertRaisesRegex(MODULE.PhaseOneFinalAcceptanceContractError, "RTO"):
            MODULE.validate_contract(changed)

    def test_acceptance_cannot_claim_portfolio_completion(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["acceptance_boundary"]["portfolio_product_complete"] = True
        with self.assertRaisesRegex(MODULE.PhaseOneFinalAcceptanceContractError, "Portfolio product"):
            MODULE.validate_contract(changed)

    def test_freeze_commit_must_remain_artifact_only(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["acceptance_boundary"]["freeze_commit_policy"] = "all-changes"
        with self.assertRaisesRegex(MODULE.PhaseOneFinalAcceptanceContractError, "freeze policy"):
            MODULE.validate_contract(changed)

    def test_forbidden_capability_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_execution_capability"] = True
        with self.assertRaisesRegex(MODULE.PhaseOneFinalAcceptanceContractError, "live_execution_capability"):
            MODULE.validate_contract(changed)

    def test_only_acceptance_execution_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P2-01"
        with self.assertRaisesRegex(MODULE.PhaseOneFinalAcceptanceContractError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
