from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_durable_jobs_outbox",
    ROOT / "scripts/verify_durable_jobs_outbox.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load durable work verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DurableJobsOutboxContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_p1_04_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_trd_bot_adapter()

    def test_candidate_is_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files()
        MODULE.validate_documents()
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

    def test_checksum_is_deterministic(self) -> None:
        reversed_contract = dict(reversed(list(self.contract.items())))
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.canonical_checksum(reversed_contract))

    def test_exactly_once_delivery_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["exactly_once_delivery_claim"] = True
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "forbidden capability"):
            MODULE.validate_contract(changed)

    def test_skip_locked_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["job_protocol"]["claim_locking"] = "plain_select"
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "claim locking"):
            MODULE.validate_contract(changed)

    def test_lost_lease_cannot_be_accepted(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["job_protocol"]["lost_lease_fails_closed"] = False
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "lost_lease"):
            MODULE.validate_contract(changed)

    def test_outbox_must_share_completion_transaction(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["outbox_protocol"]["written_in_job_completion_transaction"] = False
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "completion transaction"):
            MODULE.validate_contract(changed)

    def test_live_order_capability_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "forbidden capability"):
            MODULE.validate_contract(changed)

    def test_next_stage_is_only_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P1-06"
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "next stage"):
            MODULE.validate_contract(changed)

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "candidate SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_wrong_commit_message(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_message"] = "feat(nexora): wrong candidate"
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "commit message"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_all_primary_jobs(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        del changed["github_actions"]["jobs"]["postgresql_17"]
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "job inventory"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_failed_migration_drift_check(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["postgresql_17"]["migration_drift_check_passed"] = False
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "migration_drift_check_passed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_all_regression_workflows(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        del changed["regression_workflows"]["runtime_foundation"]
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "workflow inventory"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_regression_sha_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["regression_workflows"]["trd_bot_adapter"]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "workflow head SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_contract_drift(self) -> None:
        changed_contract = copy.deepcopy(self.contract)
        changed_contract["job_protocol"]["queue_backend"] = "memory"
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "contract checksum"):
            MODULE.validate_freeze_record(self.freeze_record, changed_contract)

    def test_freeze_record_rejects_exactly_once_claim(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["exactly_once_delivery_claimed"] = True
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "exactly_once"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p1_06(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P1-07"
        with self.assertRaisesRegex(MODULE.DurableWorkContractError, "post-freeze"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
