from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_phase_three_roadmap",
    ROOT / "scripts/verify_phase_three_roadmap.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-00 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhaseThreeRoadmapContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_phase_two_prerequisite_is_valid(self) -> None:
        MODULE.validate_phase_two_prerequisite()

    def test_server_deployment_gate_is_preserved(self) -> None:
        MODULE.validate_server_gate()

    def test_candidate_contract_and_repository_markers_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files_and_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_freeze_record_is_valid(self) -> None:
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

    def test_phase_two_freeze_cannot_be_rebound(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_two_prerequisite"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "Freeze commit drift"):
            MODULE.validate_contract(changed)

    def test_local_acceptance_cannot_claim_production_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["roadmap_amendment"]["local_acceptance_is_production_acceptance"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "local production claim"):
            MODULE.validate_contract(changed)

    def test_server_gate_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["roadmap_amendment"]["server_acceptance_is_removed"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "server gate removed"):
            MODULE.validate_contract(changed)

    def test_server_gate_cannot_be_bypassed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["roadmap_amendment"]["server_acceptance_is_bypassed"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "server gate bypassed"):
            MODULE.validate_contract(changed)

    def test_production_deployment_cannot_be_unblocked(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["roadmap_amendment"]["production_deployment_blocked"] = False
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "production deployment unblocked"):
            MODULE.validate_contract(changed)

    def test_v0_1_release_cannot_be_unblocked(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["roadmap_amendment"]["v0_1_release_blocked"] = False
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "v0.1 release unblocked"):
            MODULE.validate_contract(changed)

    def test_release_blockers_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["server_deployment_gate"]["required_before"] = ["v0.1-release"]
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "release blockers drift"):
            MODULE.validate_contract(changed)

    def test_trd_bot_0_3_0_cannot_be_marked_compatible(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["trd_bot_dependency"]["current_release_compatible"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "0.3.0"):
            MODULE.validate_contract(changed)

    def test_p3_03_provider_gate_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["trd_bot_dependency"]["p3_03_freeze_requires_compatible_provider"] = False
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "provider gate removed"):
            MODULE.validate_contract(changed)

    def test_direct_trd_bot_database_access_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["trd_bot_dependency"]["direct_database_access"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "direct TRD Bot"):
            MODULE.validate_contract(changed)

    def test_human_review_actions_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_three_boundary"]["human_review_actions"].remove("defer")
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "review actions drift"):
            MODULE.validate_contract(changed)

    def test_live_execution_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_three_boundary"]["live_execution"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "live_execution"):
            MODULE.validate_contract(changed)

    def test_phase_three_stage_order_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_three_roadmap"][1], changed["phase_three_roadmap"][2] = (
            changed["phase_three_roadmap"][2],
            changed["phase_three_roadmap"][1],
        )
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "stage order drift"):
            MODULE.validate_contract(changed)

    def test_later_stage_cannot_be_opened_before_p3_00_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_three_roadmap"][1]["status"] = "candidate"
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "must remain planned"):
            MODULE.validate_contract(changed)

    def test_acceptance_requirement_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_three_acceptance"]["compatible_provider_smoke_required"] = False
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "requirement disabled"):
            MODULE.validate_contract(changed)

    def test_forbidden_capability_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "forbidden capability"):
            MODULE.validate_contract(changed)

    def test_only_p3_00_freeze_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P3-01"
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "next stage drift"):
            MODULE.validate_contract(changed)

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "candidate SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_a_different_candidate_tree(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_tree_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "candidate tree drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_successful_primary_ci(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "did not succeed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_all_regression_workflows(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["regression_workflows"].pop("contracts")
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "workflow inventory mismatch"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_regression_sha_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["regression_workflows"]["contracts"]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "head SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_cannot_remove_server_gate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["server_deployment_acceptance"]["removed"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "server gate was removed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_cannot_bypass_server_gate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["server_deployment_acceptance"]["bypassed"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "server gate was bypassed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_cannot_claim_production_readiness(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["production_readiness_claimed"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "production readiness"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_cannot_enable_live_orders(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "live_order_capability"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p3_01(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P3-02"
        with self.assertRaisesRegex(MODULE.PhaseThreeRoadmapError, "post-Freeze stage drift"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
