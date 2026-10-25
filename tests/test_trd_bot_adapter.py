from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_trd_bot_adapter",
    ROOT / "scripts/verify_trd_bot_adapter.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load TRD Bot adapter verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TrdBotAdapterContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_postgresql_schema_is_valid(self) -> None:
        MODULE.validate_frozen_postgresql_schema()

    def test_candidate_is_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files()
        MODULE.validate_documents()
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

    def test_checksum_is_deterministic(self) -> None:
        reversed_contract = dict(reversed(list(self.contract.items())))
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.canonical_checksum(reversed_contract))

    def test_postgresql_freeze_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["postgresql_schema_prerequisite"]["freeze_record_checksum"] = "0" * 64
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "freeze checksum"):
            MODULE.validate_contract(changed)

    def test_trd_bot_0_3_0_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["compatibility"]["provider_0_3_0_status"] = "compatible"
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "0.3.0"):
            MODULE.validate_contract(changed)

    def test_provider_range_cannot_expand_without_review(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["compatibility"]["provider_release_range"] = ">=0.3.1"
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "provider range"):
            MODULE.validate_contract(changed)

    def test_capability_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["compatibility"]["commands"].pop()
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "command capability"):
            MODULE.validate_contract(changed)

    def test_operation_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["interface"]["operations"].pop()
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "operation inventory"):
            MODULE.validate_contract(changed)

    def test_retry_attempt_budget_cannot_expand(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["retry_policy"]["maximum_attempts"] = 10
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "attempt budget"):
            MODULE.validate_contract(changed)

    def test_exactly_once_delivery_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["exactly_once_delivery_claim"] = True
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "exactly_once"):
            MODULE.validate_contract(changed)

    def test_direct_database_access_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["direct_trd_bot_database_access"] = True
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "direct_trd_bot"):
            MODULE.validate_contract(changed)

    def test_live_orders_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "live_order"):
            MODULE.validate_contract(changed)

    def test_runtime_registration_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["delivery"]["runtime_composition_registered"] = True
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "runtime_composition"):
            MODULE.validate_contract(changed)

    def test_live_provider_smoke_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["delivery"]["live_provider_smoke_claimed"] = True
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "live_provider"):
            MODULE.validate_contract(changed)

    def test_production_https_cannot_be_weakened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["configuration"]["production_transport"] = "http"
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "HTTPS"):
            MODULE.validate_contract(changed)

    def test_next_stage_is_only_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P1-05"
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "next stage"):
            MODULE.validate_contract(changed)

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "candidate SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_wrong_commit_message(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_message"] = "feat(nexora): wrong candidate"
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "commit message"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_both_adapter_jobs(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        del changed["github_actions"]["jobs"]["backend"]
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "job inventory"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_failed_typecheck(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["backend"]["typecheck_passed"] = False
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "typecheck_passed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_external_network_claim(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["backend"]["external_network_used"] = True
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "external network"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_all_regression_workflows(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        del changed["regression_workflows"]["postgresql_schema"]
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "regression workflow inventory"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_regression_sha_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["regression_workflows"]["contracts"]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "workflow head SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_contract_drift(self) -> None:
        changed_contract = copy.deepcopy(self.contract)
        changed_contract["retry_policy"]["maximum_attempts"] = 3
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "contract checksum"):
            MODULE.validate_freeze_record(self.freeze_record, changed_contract)

    def test_freeze_record_rejects_postgresql_prerequisite_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["postgresql_schema_prerequisite"]["freeze_record_checksum"] = "0" * 64
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "freeze record checksum"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p1_05(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P1-06"
        with self.assertRaisesRegex(MODULE.TrdBotAdapterContractError, "post-freeze next stage"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
