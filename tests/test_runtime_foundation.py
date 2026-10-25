from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_runtime_foundation",
    ROOT / "scripts/verify_runtime_foundation.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load runtime foundation verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RuntimeFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_phase_zero_is_valid(self) -> None:
        MODULE.validate_frozen_phase_zero()

    def test_candidate_is_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files(self.contract)
        MODULE.validate_documents()
        MODULE.validate_freeze_record(self.freeze_record, self.contract)

    def test_checksum_is_deterministic(self) -> None:
        reversed_contract = dict(reversed(list(self.contract.items())))
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.canonical_checksum(reversed_contract))

    def test_production_readiness_is_rejected(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["delivery"]["production_readiness_claimed"] = True
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "production_readiness"):
            MODULE.validate_contract(changed)

    def test_database_runtime_is_rejected(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["delivery"]["database_runtime_delivered"] = True
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "database_runtime"):
            MODULE.validate_contract(changed)

    def test_live_orders_are_rejected(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "live_order"):
            MODULE.validate_contract(changed)

    def test_direct_database_access_is_rejected(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["direct_trd_bot_database_access"] = True
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "direct_trd"):
            MODULE.validate_contract(changed)

    def test_autonomous_ai_is_rejected(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["autonomous_ai_execution"] = True
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "autonomous_ai"):
            MODULE.validate_contract(changed)

    def test_persian_remains_default(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["web_runtime"]["default_locale"] = "en"
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "Persian"):
            MODULE.validate_contract(changed)

    def test_persian_remains_rtl(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["design_foundation"]["locales"]["fa"]["direction"] = "ltr"
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "RTL"):
            MODULE.validate_contract(changed)

    def test_theme_inventory_cannot_shrink(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["design_foundation"]["themes"].pop()
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "theme"):
            MODULE.validate_contract(changed)

    def test_next_stage_is_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P1-02"
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "next stage"):
            MODULE.validate_contract(changed)

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "candidate SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_wrong_commit_message(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_message"] = "feat(nexora): wrong candidate"
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "commit message"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_all_three_jobs(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        del changed["github_actions"]["jobs"]["web"]
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "all three"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_failed_job(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["backend"]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "was not successful"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_wrong_job_id(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["foundation_contract"]["job_id"] = 0
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "job ID"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_production_build_evidence(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["github_actions"]["jobs"]["web"]["production_build_passed"] = False
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "production_build_passed"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_contract_drift(self) -> None:
        changed_contract = copy.deepcopy(self.contract)
        changed_contract["toolchain"]["node"] = "changed"
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "contract checksum"):
            MODULE.validate_freeze_record(self.freeze_record, changed_contract)

    def test_freeze_record_rejects_phase_zero_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["phase_zero_prerequisite"]["freeze_record_checksum"] = "0" * 64
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "Phase 0 freeze record checksum"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p1_02(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P1-03"
        with self.assertRaisesRegex(MODULE.RuntimeFoundationError, "post-freeze next stage"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
