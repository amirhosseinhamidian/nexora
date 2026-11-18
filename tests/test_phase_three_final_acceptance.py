from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_phase_three_final_acceptance",
    ROOT / "scripts/verify_phase_three_final_acceptance.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-13 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhaseThreeFinalAcceptanceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_phase_three_chain_and_candidate_tooling_are_valid(self) -> None:
        MODULE.validate_phase_three_chain()
        MODULE.validate_p3_12_prerequisite()
        MODULE.validate_provider_smoke_source()
        MODULE.validate_contract(self.contract)
        MODULE.validate_files_and_workflow()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_p3_12_prerequisite_cannot_be_rebound(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["p3_12_prerequisite"]["accepted_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "P3-12 accepted SHA drift"):
            MODULE.validate_contract(changed)

    def test_automated_gate_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["automated_gates"].remove("postgresql_projection_recovery")
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "gate inventory"):
            MODULE.validate_contract(changed)

    def test_migration_from_zero_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_three_acceptance"]["migration_from_zero_required"] = False
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "requirement disabled"):
            MODULE.validate_contract(changed)

    def test_duplicate_delivery_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_three_acceptance"]["duplicate_delivery_required"] = False
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "requirement disabled"):
            MODULE.validate_contract(changed)

    def test_full_resync_recovery_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_three_acceptance"]["full_resync_recovery_required"] = False
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "requirement disabled"):
            MODULE.validate_contract(changed)

    def test_provider_smoke_evidence_cannot_be_rebound(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["provider_smoke_evidence"]["artifact_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "provider digest drift"):
            MODULE.validate_contract(changed)

    def test_export_coverage_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_three_acceptance"]["ai_safe_export_required"] = False
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "requirement disabled"):
            MODULE.validate_contract(changed)

    def test_server_acceptance_cannot_be_marked_complete(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["server_deployment_acceptance"]["status"] = "passed"
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "remain deferred"):
            MODULE.validate_contract(changed)

    def test_release_blockers_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["server_deployment_acceptance"]["required_before"] = ["v0.1-release"]
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "release blockers"):
            MODULE.validate_contract(changed)

    def test_freeze_commit_must_remain_artifact_only(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["acceptance_boundary"]["freeze_commit_policy"] = "all-changes"
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "freeze policy"):
            MODULE.validate_contract(changed)

    def test_production_readiness_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["production_readiness_claimed"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "production readiness"):
            MODULE.validate_contract(changed)

    def test_live_execution_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "security boundary"):
            MODULE.validate_contract(changed)

    def test_post_freeze_stage_cannot_bypass_server_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["post_freeze_stage"] = "NEX-P4-00"
        with self.assertRaisesRegex(MODULE.PhaseThreeFinalAcceptanceError, "post-Freeze stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
