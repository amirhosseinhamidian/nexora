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
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_p1_08_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p1_08()

    def test_candidate_contract_and_files_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files_and_runtime_markers()
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

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

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.TrdBotSyncRuntimeContractError, "candidate SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_wrong_commit_message(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_message"] = "fix(nexora): wrong candidate"
        with self.assertRaisesRegex(MODULE.TrdBotSyncRuntimeContractError, "commit message drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_every_primary_job(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        del changed["github_actions"]["jobs"]["postgresql_17"]
        with self.assertRaisesRegex(MODULE.TrdBotSyncRuntimeContractError, "job inventory mismatch"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_failed_atomicity_gate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["postgresql_17"]["sync_atomicity_integration_passed"] = False
        with self.assertRaisesRegex(MODULE.TrdBotSyncRuntimeContractError, "sync_atomicity_integration_passed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_every_regression_workflow(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        del changed["regression_workflows"]["runtime_api_auth"]
        with self.assertRaisesRegex(MODULE.TrdBotSyncRuntimeContractError, "workflow inventory mismatch"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_regression_sha_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["regression_workflows"]["contracts"]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.TrdBotSyncRuntimeContractError, "workflow head SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_contract_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["delivery"]["bounded_page_size"] = 1
        with self.assertRaisesRegex(MODULE.TrdBotSyncRuntimeContractError, "contract checksum mismatch"):
            MODULE.validate_freeze_record(self.freeze_record, changed)

    def test_freeze_record_cannot_claim_live_execution(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["live_execution_capability"] = True
        with self.assertRaisesRegex(MODULE.TrdBotSyncRuntimeContractError, "live_execution_capability"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p1_10(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P1-11"
        with self.assertRaisesRegex(MODULE.TrdBotSyncRuntimeContractError, "post-freeze stage drift"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
