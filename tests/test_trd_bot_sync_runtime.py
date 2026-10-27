from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_trd_bot_sync_runtime",
    ROOT / "scripts/verify_trd_bot_sync_runtime.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TrdBotSyncRuntimeContractTests(unittest.TestCase):
    def test_frozen_p1_08_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p1_08()

    def test_candidate_contract_and_files_are_valid(self) -> None:
        MODULE.validate_contract(MODULE.load_contract())
        MODULE.validate_files_and_runtime_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(MODULE.load_contract()), MODULE.CONTRACT_CHECKSUM)

    def test_handler_registration_cannot_be_removed(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["delivery"]["registered_job_types"] = ["trd_bot.event_sync"]
        with self.assertRaises(MODULE.TrdBotSyncRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_unknown_schema_quarantine_cannot_be_disabled(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["event_ingestion"]["unknown_payload_schema_behavior"] = "accept"
        with self.assertRaises(MODULE.TrdBotSyncRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_atomic_completion_cannot_be_weakened(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["transaction_boundary"]["receipt_evidence_checkpoint_outbox_and_continuation_atomic"] = False
        with self.assertRaises(MODULE.TrdBotSyncRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_live_execution_cannot_be_enabled(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["security_boundary"]["live_order_capability"] = True
        with self.assertRaises(MODULE.TrdBotSyncRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_next_stage_is_only_p1_09_freeze(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["transition"]["next_allowed_stage"] = "NEX-P1-10"
        with self.assertRaises(MODULE.TrdBotSyncRuntimeContractError):
            MODULE.validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
