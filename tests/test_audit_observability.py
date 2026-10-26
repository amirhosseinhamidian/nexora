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

    def test_frozen_p1_07_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p1_07()

    def test_candidate_contract_and_runtime_markers_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files_and_runtime_markers()

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


if __name__ == "__main__":
    unittest.main()
