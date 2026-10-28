from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_private_deployment_operations",
    ROOT / "scripts/verify_private_deployment_operations.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load private deployment operations verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PrivateDeploymentOperationsContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_p1_11_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p1_11()

    def test_candidate_contract_and_runtime_markers_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files_and_runtime_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_freeze_record_is_valid(self) -> None:
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

    def test_prerequisite_cannot_be_rebound(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["p1_11_prerequisite"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "commit drift"):
            MODULE.validate_contract(changed)

    def test_public_host_port_cannot_be_added(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["topology"]["only_host_port"] = 80
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "HTTPS 443"):
            MODULE.validate_contract(changed)

    def test_runtime_backup_cannot_count_as_offsite(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["backup"]["runtime_copy_counts_as_offsite"] = True
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "offsite"):
            MODULE.validate_contract(changed)

    def test_backup_encryption_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["backup"]["encryption"] = "none"
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "encryption"):
            MODULE.validate_contract(changed)

    def test_restore_cannot_reuse_service_tokens(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["restore"]["service_token_rotation_required"] = False
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "service_token_rotation"):
            MODULE.validate_contract(changed)

    def test_retention_cannot_delete_immutable_evidence(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["retention"]["immutable_evidence_excluded"] = False
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "immutable evidence"):
            MODULE.validate_contract(changed)

    def test_retention_scope_cannot_expand_silently(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["retention"]["automatic_deletion_scope"].append("financial_records")
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "deletion scope"):
            MODULE.validate_contract(changed)

    def test_overload_cannot_drop_evidence(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["capacity_and_overload"]["immutable_evidence_dropped"] = True
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "drop evidence"):
            MODULE.validate_contract(changed)

    def test_production_readiness_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["acceptance_boundary"]["production_readiness_claimed"] = True
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "deferred"):
            MODULE.validate_contract(changed)

    def test_forbidden_capability_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "live_order_capability"):
            MODULE.validate_contract(changed)

    def test_only_p1_12_freeze_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P1-13"
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "next stage"):
            MODULE.validate_contract(changed)

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "candidate SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_a_different_tree(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_tree_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "candidate tree drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_successful_topology_job(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["private_topology"]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "did not succeed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_operations_image_evidence(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["private_topology"]["operations_image_built"] = False
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "operations_image_built"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_regression_workflow_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["regression_workflows"]["contracts"]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "head SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_cannot_claim_production_readiness(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["production_readiness_claimed"] = True
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "production readiness"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p1_13(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P2-01"
        with self.assertRaisesRegex(MODULE.PrivateDeploymentOperationsContractError, "post-freeze stage"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
