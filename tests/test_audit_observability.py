from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_audit_observability",
    ROOT / "scripts/verify_audit_observability.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load audit observability verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AuditObservabilityContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_p1_07_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p1_07()

    def test_candidate_contract_and_runtime_markers_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files_and_runtime_markers()
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_prerequisite_cannot_be_rebound(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["p1_07_prerequisite"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "freeze commit drift"):
            MODULE.validate_contract(changed)

    def test_raw_query_logging_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["structured_logging"]["raw_query_string_logged"] = True
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "logging policy drift"):
            MODULE.validate_contract(changed)

    def test_recursive_redaction_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["structured_logging"]["secret_redaction_recursive"] = False
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "logging policy drift"):
            MODULE.validate_contract(changed)

    def test_raw_path_cannot_become_a_metric_label(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime_metrics"]["raw_path_or_query_labels_forbidden"] = False
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "raw paths"):
            MODULE.validate_contract(changed)

    def test_readiness_cannot_expose_targets(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["readiness"]["does_not_expose_targets_or_credentials"] = False
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "expose secrets"):
            MODULE.validate_contract(changed)

    def test_audit_immutability_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_audit"]["mutation_trigger_enforced"] = False
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "immutability"):
            MODULE.validate_contract(changed)

    def test_audit_retention_cannot_silently_change(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_audit"]["retention_days"] = 30
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "retention"):
            MODULE.validate_contract(changed)

    def test_public_metrics_endpoint_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["public_metrics_endpoint"] = True
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "public_metrics_endpoint"):
            MODULE.validate_contract(changed)

    def test_only_p1_08_freeze_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P1-09"
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "next stage"):
            MODULE.validate_contract(changed)

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "candidate SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_wrong_commit_message(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_message"] = "fix(nexora): wrong candidate"
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "commit message drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_every_primary_job(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        del changed["github_actions"]["jobs"]["postgresql_17"]
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "job inventory mismatch"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_failed_migration_drift_check(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["postgresql_17"]["migration_drift_check_passed"] = False
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "migration_drift_check_passed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_every_regression_workflow(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        del changed["regression_workflows"]["runtime_api_auth"]
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "workflow inventory mismatch"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_regression_sha_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["regression_workflows"]["contracts"]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "workflow head SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_contract_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime_metrics"]["maximum_route_dimensions"] = 1
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "contract checksum mismatch"):
            MODULE.validate_freeze_record(self.freeze_record, changed)

    def test_freeze_record_cannot_claim_production_readiness(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["production_readiness_claimed"] = True
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "production_readiness_claimed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p1_09(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P1-10"
        with self.assertRaisesRegex(MODULE.AuditObservabilityContractError, "post-freeze stage drift"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
