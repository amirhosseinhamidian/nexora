from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_phase_one_readiness",
    ROOT / "scripts/verify_phase_one_readiness.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load Phase 1 readiness verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhaseOneReadinessContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_p1_06_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p1_06()

    def test_candidate_contract_files_and_document_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files()
        MODULE.validate_documents()

    def test_checksum_is_deterministic(self) -> None:
        reversed_contract = dict(reversed(list(self.contract.items())))
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.canonical_checksum(reversed_contract))

    def test_phase_one_cannot_be_marked_ready(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["assessment"]["phase_one_ready"] = True
        with self.assertRaisesRegex(MODULE.PhaseOneReadinessError, "phase_one_ready"):
            MODULE.validate_contract(changed)

    def test_final_acceptance_cannot_stop_being_deferred(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["assessment"]["final_acceptance_deferred"] = False
        with self.assertRaisesRegex(MODULE.PhaseOneReadinessError, "final_acceptance_deferred"):
            MODULE.validate_contract(changed)

    def test_stage_cannot_be_falsely_marked_complete(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["stage_matrix"][8]["status"] = "complete"
        with self.assertRaisesRegex(MODULE.PhaseOneReadinessError, "P1-09"):
            MODULE.validate_contract(changed)

    def test_gap_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["gaps"].pop()
        with self.assertRaisesRegex(MODULE.PhaseOneReadinessError, "nine blocking gaps"):
            MODULE.validate_contract(changed)

    def test_gap_cannot_be_made_non_blocking(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["gaps"][0]["blocking"] = False
        with self.assertRaisesRegex(MODULE.PhaseOneReadinessError, "non-blocking"):
            MODULE.validate_contract(changed)

    def test_gap_owner_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["gaps"][0]["owner_stage"] = "NEX-P1-08"
        with self.assertRaisesRegex(MODULE.PhaseOneReadinessError, "gap owner"):
            MODULE.validate_contract(changed)

    def test_roadmap_cannot_skip_a_stage(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["revised_roadmap"].pop(3)
        with self.assertRaisesRegex(MODULE.PhaseOneReadinessError, "seven stages"):
            MODULE.validate_contract(changed)

    def test_forbidden_capability_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_execution_capability"] = True
        with self.assertRaisesRegex(MODULE.PhaseOneReadinessError, "forbidden capability"):
            MODULE.validate_contract(changed)

    def test_next_stage_is_only_reconciliation_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P1-07"
        with self.assertRaisesRegex(MODULE.PhaseOneReadinessError, "freeze"):
            MODULE.validate_contract(changed)

    def test_post_freeze_stage_is_only_p1_07(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["post_freeze_stage"] = "NEX-P2-01"
        with self.assertRaisesRegex(MODULE.PhaseOneReadinessError, "post-freeze"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
