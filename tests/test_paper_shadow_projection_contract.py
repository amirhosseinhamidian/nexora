from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_paper_shadow_projection", ROOT / "scripts/verify_paper_shadow_projection.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PaperShadowProjectionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze = MODULE.load_freeze_record()

    def test_frozen_p2_07_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p2_07()

    def test_candidate_contract_runtime_and_workflow_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_runtime_markers()
        MODULE.validate_workflow()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_freeze_record_is_valid(self) -> None:
        MODULE.validate_freeze_record(self.freeze, self.contract)
        MODULE.validate_workflow()

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PaperShadowProjectionContractError, "candidate SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_a_failed_check(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["checks"][0]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.PaperShadowProjectionContractError, "check evidence"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p2_09(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["next_allowed_stage"] = "NEX-P2-10"
        with self.assertRaisesRegex(MODULE.PaperShadowProjectionContractError, "next stage"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_live_mode_cannot_enter_p2_08(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["live_mode_included"] = True
        with self.assertRaisesRegex(MODULE.PaperShadowProjectionContractError, "live_mode"):
            MODULE.validate_contract(changed)

    def test_projection_cannot_mutate_the_journal(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["projection_invariants"]["projection_writes_transaction_journal"] = True
        with self.assertRaisesRegex(MODULE.PaperShadowProjectionContractError, "transaction_journal"):
            MODULE.validate_contract(changed)

    def test_aggregate_gap_cannot_be_silently_accepted(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["projection_invariants"]["gap_marks_projection_incomplete"] = False
        with self.assertRaisesRegex(MODULE.PaperShadowProjectionContractError, "gap_marks"):
            MODULE.validate_contract(changed)

    def test_public_api_cannot_enter_before_p2_09(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime_boundary"]["new_http_operations"] = ["GET /v1/trd-bot/projection"]
        with self.assertRaisesRegex(MODULE.PaperShadowProjectionContractError, "HTTP"):
            MODULE.validate_contract(changed)

    def test_freeze_transition_cannot_be_skipped(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P2-09"
        with self.assertRaisesRegex(MODULE.PaperShadowProjectionContractError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
