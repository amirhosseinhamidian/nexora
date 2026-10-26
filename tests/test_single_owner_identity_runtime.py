from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_single_owner_identity_runtime",
    ROOT / "scripts/verify_single_owner_identity_runtime.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SingleOwnerIdentityRuntimeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_p1_05_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_durable_jobs()

    def test_candidate_contract_files_and_documents_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files()
        MODULE.validate_documents()
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

    def test_live_capability_cannot_be_enabled(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["security_boundary"]["live_order_capability"] = True
        with self.assertRaises(MODULE.IdentityRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_session_token_cannot_be_marked_persisted(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["sessions"]["raw_token_persisted"] = True
        with self.assertRaises(MODULE.IdentityRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_passkey_private_key_cannot_be_persisted(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["webauthn"]["private_key_persisted"] = True
        with self.assertRaises(MODULE.IdentityRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_cbor_compatibility_pin_cannot_drift(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["webauthn"]["cbor2_compatibility_version"] = "6.1.5"
        with self.assertRaises(MODULE.IdentityRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_infrastructure_environment_allowlist_cannot_expand(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["private_runtime"]["base_loader_external_environment_allowlist"].append("NEXORA_DATABASE_URL")
        with self.assertRaises(MODULE.IdentityRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_next_stage_is_only_freeze(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["transition"]["next_allowed_stage"] = "NEX-P2-01"
        with self.assertRaises(MODULE.IdentityRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        record = copy.deepcopy(self.freeze_record)
        record["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.IdentityRuntimeContractError, "candidate SHA"):
            MODULE.validate_freeze_record(record, self.contract)

    def test_freeze_record_rejects_wrong_commit_message(self) -> None:
        record = copy.deepcopy(self.freeze_record)
        record["candidate_commit_message"] = "feat(nexora): wrong candidate"
        with self.assertRaisesRegex(MODULE.IdentityRuntimeContractError, "commit message"):
            MODULE.validate_freeze_record(record, self.contract)

    def test_freeze_record_requires_all_primary_jobs(self) -> None:
        record = copy.deepcopy(self.freeze_record)
        del record["github_actions"]["jobs"]["private_topology"]
        with self.assertRaisesRegex(MODULE.IdentityRuntimeContractError, "job inventory"):
            MODULE.validate_freeze_record(record, self.contract)

    def test_freeze_record_rejects_failed_migration_drift_check(self) -> None:
        record = copy.deepcopy(self.freeze_record)
        record["github_actions"]["jobs"]["postgresql_17"]["migration_drift_check_passed"] = False
        with self.assertRaisesRegex(MODULE.IdentityRuntimeContractError, "migration_drift_check_passed"):
            MODULE.validate_freeze_record(record, self.contract)

    def test_freeze_record_requires_all_regression_workflows(self) -> None:
        record = copy.deepcopy(self.freeze_record)
        del record["regression_workflows"]["contracts"]
        with self.assertRaisesRegex(MODULE.IdentityRuntimeContractError, "workflow inventory"):
            MODULE.validate_freeze_record(record, self.contract)

    def test_freeze_record_rejects_regression_sha_drift(self) -> None:
        record = copy.deepcopy(self.freeze_record)
        record["regression_workflows"]["runtime_foundation"]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.IdentityRuntimeContractError, "workflow head SHA"):
            MODULE.validate_freeze_record(record, self.contract)

    def test_freeze_record_rejects_contract_drift(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["sessions"]["idle_timeout_seconds"] = 1
        with self.assertRaisesRegex(MODULE.IdentityRuntimeContractError, "contract checksum"):
            MODULE.validate_freeze_record(self.freeze_record, contract)

    def test_freeze_record_cannot_claim_production_readiness(self) -> None:
        record = copy.deepcopy(self.freeze_record)
        record["production_readiness_claimed"] = True
        with self.assertRaisesRegex(MODULE.IdentityRuntimeContractError, "production_readiness_claimed"):
            MODULE.validate_freeze_record(record, self.contract)

    def test_freeze_record_opens_only_phase_one_acceptance(self) -> None:
        record = copy.deepcopy(self.freeze_record)
        record["next_allowed_stage"] = "NEX-P2-01"
        with self.assertRaisesRegex(MODULE.IdentityRuntimeContractError, "post-freeze"):
            MODULE.validate_freeze_record(record, self.contract)


if __name__ == "__main__":
    unittest.main()
