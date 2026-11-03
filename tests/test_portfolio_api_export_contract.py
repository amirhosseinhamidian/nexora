from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_portfolio_api_export", ROOT / "scripts/verify_portfolio_api_export.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PortfolioApiExportContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze = MODULE.load_freeze_record()

    def test_frozen_p2_08_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p2_08()

    def test_candidate_contract_runtime_and_workflow_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_runtime_markers()
        MODULE.validate_workflow()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_freeze_record_is_valid(self) -> None:
        MODULE.validate_freeze_record(self.freeze, self.contract)
        MODULE.validate_workflow()

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PortfolioApiExportContractError, "candidate SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_a_failed_check(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["checks"][0]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.PortfolioApiExportContractError, "check evidence"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p2_10(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["next_allowed_stage"] = "NEX-P2-11"
        with self.assertRaisesRegex(MODULE.PortfolioApiExportContractError, "next stage"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_public_download_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["api_boundary"]["public_url_returned"] = True
        with self.assertRaisesRegex(MODULE.PortfolioApiExportContractError, "public export URL"):
            MODULE.validate_contract(changed)

    def test_partial_exports_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["export_invariants"]["partial_export_forbidden"] = False
        with self.assertRaisesRegex(MODULE.PortfolioApiExportContractError, "partial_export"):
            MODULE.validate_contract(changed)

    def test_binary_float_cannot_enter_export_contract(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["export_invariants"]["binary_float_forbidden"] = False
        with self.assertRaisesRegex(MODULE.PortfolioApiExportContractError, "binary_float"):
            MODULE.validate_contract(changed)

    def test_ai_safe_profile_cannot_omit_security_exclusions(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["profile_boundary"]["ai_safe_excluded_categories"].remove("session_identifiers")
        with self.assertRaisesRegex(MODULE.PortfolioApiExportContractError, "AI-safe"):
            MODULE.validate_contract(changed)

    def test_owner_override_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["api_boundary"]["owner_id_accepted_from_request"] = True
        with self.assertRaisesRegex(MODULE.PortfolioApiExportContractError, "owner override"):
            MODULE.validate_contract(changed)

    def test_dashboard_cannot_enter_before_p2_10(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["dashboard_included"] = True
        with self.assertRaisesRegex(MODULE.PortfolioApiExportContractError, "dashboard"):
            MODULE.validate_contract(changed)

    def test_freeze_transition_cannot_be_skipped(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P2-10"
        with self.assertRaisesRegex(MODULE.PortfolioApiExportContractError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
