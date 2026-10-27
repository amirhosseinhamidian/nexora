from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_authenticated_web_shell",
    ROOT / "scripts/verify_authenticated_web_shell.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load authenticated Web shell verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AuthenticatedWebShellContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_p1_10_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p1_10()

    def test_candidate_contract_and_runtime_markers_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files_and_runtime_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_freeze_record_is_valid(self) -> None:
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

    def test_prerequisite_cannot_be_rebound(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["p1_10_prerequisite"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "commit drift"):
            MODULE.validate_contract(changed)

    def test_password_login_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["identity_experience"]["password_login"] = True
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "password_login"):
            MODULE.validate_contract(changed)

    def test_session_token_cannot_enter_browser_storage(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["identity_experience"]["browser_session_token_storage"] = True
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "browser_session_token_storage"):
            MODULE.validate_contract(changed)

    def test_cross_origin_api_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["browser_transport"]["external_api_target_allowed"] = True
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "external_api_target_allowed"):
            MODULE.validate_contract(changed)

    def test_production_unsafe_inline_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["content_security"]["production_unsafe_inline"] = True
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "unsafe-inline"):
            MODULE.validate_contract(changed)

    def test_export_download_cannot_escape_export_namespace(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["authenticated_export_download"]["namespace"] = "source"
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "namespace drift"):
            MODULE.validate_contract(changed)

    def test_public_artifact_access_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["public_artifact_access"] = True
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "public_artifact_access"):
            MODULE.validate_contract(changed)

    def test_portfolio_domain_routes_remain_deferred(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["routes"]["portfolio_domain_routes_enabled"] = True
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "Portfolio routes"):
            MODULE.validate_contract(changed)

    def test_only_p1_11_freeze_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P1-12"
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "next stage"):
            MODULE.validate_contract(changed)

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "candidate SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_a_different_tree(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_tree_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "candidate tree drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_wrong_commit_message(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_message"] = "test: different candidate"
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "commit message drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_successful_browser_job(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["browser"]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "did not succeed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_browser_lifecycle_evidence(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["browser"]["browser_lifecycle_tests_passed"] = False
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "browser_lifecycle"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_regression_workflow_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["regression_workflows"]["contracts"]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "head SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_cannot_enable_public_artifact_access(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["public_artifact_access"] = True
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "public_artifact_access"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p1_12(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P1-13"
        with self.assertRaisesRegex(MODULE.AuthenticatedWebShellContractError, "post-freeze stage"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
