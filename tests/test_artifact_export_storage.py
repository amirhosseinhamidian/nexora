from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_artifact_export_storage",
    ROOT / "scripts/verify_artifact_export_storage.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load artifact export storage verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ArtifactExportStorageContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_p1_09_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p1_09()

    def test_candidate_contract_and_runtime_markers_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files_and_runtime_markers()

    def test_freeze_record_is_valid(self) -> None:
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_prerequisite_cannot_be_rebound(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["p1_09_prerequisite"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "commit drift"):
            MODULE.validate_contract(changed)

    def test_public_artifact_access_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["adapter"]["public_network_access"] = True
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "cannot be public"):
            MODULE.validate_contract(changed)

    def test_atomic_publication_cannot_be_weakened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["publication"]["atomic_strategy"] = "write_directly"
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "atomic strategy"):
            MODULE.validate_contract(changed)

    def test_partial_export_cannot_be_accepted(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["export_bundle"]["partial_export_accepted"] = True
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "partial export"):
            MODULE.validate_contract(changed)

    def test_hard_quota_cannot_be_relaxed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["capacity"]["hard_quota_gib"] = 200
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "hard quota drift"):
            MODULE.validate_contract(changed)

    def test_immutable_evidence_auto_delete_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["retention"]["immutable_source_evidence_auto_delete"] = True
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "immutable_source"):
            MODULE.validate_contract(changed)

    def test_reconciliation_cannot_delete_evidence(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["reconciliation"]["automatic_evidence_deletion"] = True
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "cannot delete"):
            MODULE.validate_contract(changed)

    def test_cloud_credentials_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["cloud_storage_credentials"] = True
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "cloud_storage_credentials"):
            MODULE.validate_contract(changed)

    def test_unauthenticated_download_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime"]["unauthenticated_download_route"] = True
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "unauthenticated"):
            MODULE.validate_contract(changed)

    def test_only_p1_10_freeze_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P1-11"
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "next stage"):
            MODULE.validate_contract(changed)

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "candidate SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_wrong_commit_message(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_message"] = "feat: different candidate"
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "commit message drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_successful_primary_workflow(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "did not succeed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_exact_primary_jobs(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"].pop("storage_runtime")
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "job inventory"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_regression_workflow_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["regression_workflows"]["contracts"]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "head SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_cannot_enable_public_artifact_access(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["public_artifact_access"] = True
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "public_artifact_access"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p1_11(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P1-12"
        with self.assertRaisesRegex(MODULE.ArtifactExportStorageContractError, "post-freeze stage"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
