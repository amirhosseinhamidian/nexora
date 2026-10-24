from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_integration_contracts",
    ROOT / "scripts" / "verify_integration_contracts.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load integration contract verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class IntegrationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.matrix = MODULE.load_matrix()
        self.inventory = MODULE.load_inventory()
        self.openapi = MODULE.load_openapi()
        self.schemas = MODULE.load_schemas()
        self.fixtures = MODULE.load_fixtures()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_p0_02_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_baseline()

    def test_frozen_contract_and_evidence_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_matrix(self.matrix)
        MODULE.validate_inventory(self.inventory)
        MODULE.validate_openapi(self.openapi, self.contract)
        MODULE.validate_schemas(self.schemas)
        MODULE.validate_fixtures(self.fixtures, self.contract)
        MODULE.validate_documents()
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

    def test_contract_checksum_is_deterministic(self) -> None:
        reversed_contract = dict(reversed(list(self.contract.items())))
        self.assertEqual(
            MODULE.canonical_checksum(self.contract),
            MODULE.canonical_checksum(reversed_contract),
        )

    def test_trd_bot_0_3_0_cannot_be_marked_compatible(self) -> None:
        changed = copy.deepcopy(self.matrix)
        changed["entries"][1]["status"] = "compatible"
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "0.3.0 cannot be compatible"):
            MODULE.validate_matrix(changed)

    def test_direct_database_access_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["direct_database_access"] = True
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "direct_database_access"):
            MODULE.validate_contract(changed)

    def test_exactly_once_delivery_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["contract"]["delivery_semantics"] = "exactly_once"
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "delivery_semantics"):
            MODULE.validate_contract(changed)

    def test_unknown_schema_cannot_be_accepted(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["contract"]["unknown_schema_behavior"] = "accept"
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "unknown_schema_behavior"):
            MODULE.validate_contract(changed)

    def test_post_retry_requires_idempotency_key(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["retry_policy"]["post_retry_requires_idempotency_key"] = False
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "idempotency key"):
            MODULE.validate_contract(changed)

    def test_expired_cursor_requires_full_snapshot_resync(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["event_feed"]["cursor_expiry_action"] = "continue"
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "full snapshot resync"):
            MODULE.validate_contract(changed)

    def test_partial_export_cannot_be_accepted(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["export"]["accepted_completion_status"] = "partial"
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "partial export"):
            MODULE.validate_contract(changed)

    def test_openapi_has_exact_operations_and_no_live_capability(self) -> None:
        MODULE.validate_openapi(self.openapi, self.contract)
        operation_ids = {
            operation["operationId"]
            for path_item in self.openapi["paths"].values()
            for method, operation in path_item.items()
            if method in {"get", "post"}
        }
        self.assertEqual(len(operation_ids), 8)

    def test_openapi_rejects_a_missing_operation(self) -> None:
        changed = copy.deepcopy(self.openapi)
        del changed["paths"]["/api/v1/integration/nexora/events/{event_id}"]
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "operation inventory"):
            MODULE.validate_openapi(changed, self.contract)

    def test_fixture_secret_key_is_rejected(self) -> None:
        changed = copy.deepcopy(self.fixtures)
        changed["decision-event.json"]["payload"]["api_secret"] = "must-not-exist"
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "secret-bearing fixture key"):
            MODULE.validate_fixtures(changed, self.contract)

    def test_unknown_event_type_is_rejected(self) -> None:
        changed = copy.deepcopy(self.fixtures)
        changed["decision-event.json"]["event_type"] = "order.executed.v1"
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "event fixture type"):
            MODULE.validate_fixtures(changed, self.contract)

    def test_invalid_export_file_checksum_is_rejected(self) -> None:
        changed = copy.deepcopy(self.fixtures)
        changed["export-manifest.json"]["files"][0]["sha256"] = "invalid"
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "manifest file checksum"):
            MODULE.validate_fixtures(changed, self.contract)

    def test_root_schemas_must_remain_closed(self) -> None:
        changed = copy.deepcopy(self.schemas)
        changed["event-envelope.schema.json"]["additionalProperties"] = True
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "root schema must be closed"):
            MODULE.validate_schemas(changed)

    def test_next_stage_is_only_p0_03_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["next_allowed_stage"] = "NEX-P0-04"
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "P0-03-FREEZE"):
            MODULE.validate_contract(changed)

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "candidate SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_wrong_commit_message(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_message"] = "chore(nexora): freeze NEX-P0-02 technical baseline"
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "commit message"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_all_successful_jobs(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["integration_contract"]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "was not successful"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_a_different_job(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["integration_contract"]["job_id"] = 0
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "job ID"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_contract_drift(self) -> None:
        changed_contract = copy.deepcopy(self.contract)
        changed_contract["retry_policy"]["maximum_attempts"] = 5
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "checksum mismatch"):
            MODULE.validate_freeze_record(self.freeze_record, changed_contract)

    def test_freeze_record_rejects_baseline_prerequisite_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["technical_baseline_prerequisite"]["contract_checksum"] = "0" * 64
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "baseline prerequisite checksum"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_scope_prerequisite_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["scope_prerequisite"]["contract_checksum"] = "0" * 64
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "scope prerequisite checksum"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p0_04(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P1-01"
        with self.assertRaisesRegex(MODULE.IntegrationContractError, "frozen next stage"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
