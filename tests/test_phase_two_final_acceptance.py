from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_phase_two_final_acceptance",
    ROOT / "scripts/verify_phase_two_final_acceptance.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load Phase 2 final acceptance verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhaseTwoFinalAcceptanceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_p2_11_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p2_11()

    def test_candidate_contract_and_tooling_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files_and_runtime_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_prerequisite_cannot_be_rebound(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["p2_11_prerequisite"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "Freeze commit drift"):
            MODULE.validate_contract(changed)

    def test_evidence_freshness_cannot_be_relaxed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["evidence"]["maximum_age_days"] = 30
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "freshness"):
            MODULE.validate_contract(changed)

    def test_destructive_database_cannot_target_development(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["destructive_database_boundary"]["required_database_name"] = "nexora"
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "database drift"):
            MODULE.validate_contract(changed)

    def test_postgresql_accounting_gate_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["automated_gates"].remove("postgresql_accounting")
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "gate inventory"):
            MODULE.validate_contract(changed)

    def test_projection_rebuild_evidence_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["portfolio_acceptance"]["projection_rebuild_required"] = False
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "requirement disabled"):
            MODULE.validate_contract(changed)

    def test_atomic_publication_evidence_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["portfolio_acceptance"]["atomic_publication_required"] = False
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "requirement disabled"):
            MODULE.validate_contract(changed)

    def test_local_acceptance_cannot_claim_remote_access(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["local_reference_acceptance"]["loopback_remote_access_allowed"] = True
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "remote access"):
            MODULE.validate_contract(changed)

    def test_server_acceptance_cannot_be_marked_complete(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["server_deployment_acceptance"]["status"] = "passed"
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "remain deferred"):
            MODULE.validate_contract(changed)

    def test_release_blockers_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["server_deployment_acceptance"]["required_before"] = ["v0.1-release"]
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "release blockers"):
            MODULE.validate_contract(changed)

    def test_freeze_commit_must_remain_artifact_only(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["acceptance_boundary"]["freeze_commit_policy"] = "all-changes"
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "freeze policy"):
            MODULE.validate_contract(changed)

    def test_forbidden_capability_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "live_order_capability"):
            MODULE.validate_contract(changed)

    def test_only_acceptance_execution_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P3-01"
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "next stage"):
            MODULE.validate_contract(changed)

    def test_post_freeze_stage_remains_server_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["post_freeze_stage"] = "NEX-P3-01"
        with self.assertRaisesRegex(MODULE.PhaseTwoFinalAcceptanceContractError, "post-Freeze"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
