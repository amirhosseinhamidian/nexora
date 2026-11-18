from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_phase_four_product_experience_roadmap",
    ROOT / "scripts/verify_phase_four_product_experience_roadmap.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P4-00 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhaseFourProductExperienceRoadmapContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_phase_three_prerequisite_is_valid(self) -> None:
        MODULE.validate_phase_three_prerequisite()

    def test_candidate_contract_and_repository_markers_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files_and_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_phase_three_freeze_cannot_be_rebound(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_three_prerequisite"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "Freeze commit drift"):
            MODULE.validate_contract(changed)

    def test_frozen_repository_truth_remains_highest_priority(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["source_hierarchy"].reverse()
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "priority drift"):
            MODULE.validate_contract(changed)

    def test_phase_number_cannot_become_product_version(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["reconciliation_decision"]["phase_number_is_not_product_version"] = False
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "phase/version"):
            MODULE.validate_contract(changed)

    def test_backend_reimplementation_cannot_be_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["reconciliation_decision"]["backend_domain_reimplementation_allowed"] = True
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "reimplementation"):
            MODULE.validate_contract(changed)

    def test_product_must_be_usable_without_direct_api_calls(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["reconciliation_decision"]["existing_capabilities_must_become_usable_without_direct_api_calls"] = False
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "direct-API"):
            MODULE.validate_contract(changed)

    def test_persian_sidebar_cannot_move_left(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["product_experience_requirements"]["persian_sidebar_side"] = "left"
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "Persian Sidebar"):
            MODULE.validate_contract(changed)

    def test_first_run_onboarding_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["product_experience_requirements"]["first_run_onboarding_required"] = False
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "first_run_onboarding"):
            MODULE.validate_contract(changed)

    def test_plain_persian_content_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["product_experience_requirements"]["persian_avoids_unnecessary_english_required"] = False
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "unnecessary_english"):
            MODULE.validate_contract(changed)

    def test_required_micro_component_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["micro_component_inventory"].remove("confirmation_dialog")
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "micro-component"):
            MODULE.validate_contract(changed)

    def test_physical_evidence_deletion_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["destructive_and_sensitive_action_policy"]["physical_delete_of_immutable_evidence"] = True
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "physical evidence deletion"):
            MODULE.validate_contract(changed)

    def test_phase_four_stage_order_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_four_roadmap"][1], changed["phase_four_roadmap"][2] = (
            changed["phase_four_roadmap"][2],
            changed["phase_four_roadmap"][1],
        )
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "stage order drift"):
            MODULE.validate_contract(changed)

    def test_later_stage_cannot_open_before_p4_00_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_four_roadmap"][1]["status"] = "candidate"
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "must remain planned"):
            MODULE.validate_contract(changed)

    def test_assistant_execution_rule_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["stage_execution_policy"]["assistant_runs_tests_builds_or_migrations"] = True
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "assistant execution"):
            MODULE.validate_contract(changed)

    def test_roadmap_change_after_freeze_requires_amendment(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["stage_execution_policy"]["roadmap_change_after_freeze_requires_amendment"] = False
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "amendment"):
            MODULE.validate_contract(changed)

    def test_forbidden_capability_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "forbidden capability"):
            MODULE.validate_contract(changed)

    def test_server_gate_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["server_deployment_gate"]["removed"] = True
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "server gate removed"):
            MODULE.validate_contract(changed)

    def test_only_p4_00_freeze_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P4-01"
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "next stage drift"):
            MODULE.validate_contract(changed)

    def test_word_roadmap_must_follow_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["word_roadmap_generated_after_freeze"] = False
        with self.assertRaisesRegex(MODULE.PhaseFourProductExperienceRoadmapError, "Word generation"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
