from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_phase_four_product_acceptance", ROOT / "scripts/verify_phase_four_product_acceptance.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P4-11 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProductAcceptanceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.identity = {"candidate_commit_sha": "a" * 40, "candidate_tree_sha": "b" * 40}

    def test_candidate_has_frozen_prerequisite_and_repository_checks(self) -> None:
        MODULE.validate_prerequisite(self.contract)
        MODULE.validate_repository(self.contract)

    def test_freeze_binds_ci_and_manual_review_to_the_candidate(self) -> None:
        MODULE.validate_freeze_record(MODULE.load_json(MODULE.FREEZE_PATH), self.contract)

    def test_freeze_rejects_browser_evidence_from_another_candidate(self) -> None:
        record = MODULE.load_json(MODULE.FREEZE_PATH)
        record["browser_evidence"]["candidate_commit_sha"] = "c" * 40
        with self.assertRaisesRegex(MODULE.ProductAcceptanceError, "browser evidence candidate_commit_sha"):
            MODULE.validate_freeze_record(record, self.contract)

    def test_freeze_requires_an_explicit_pass_for_every_manual_profile(self) -> None:
        record = MODULE.load_json(MODULE.FREEZE_PATH)
        record["manual_visual"]["record"]["results"][0]["result"] = "pending"
        with self.assertRaisesRegex(MODULE.ProductAcceptanceError, "manual profiles awaiting a pass"):
            MODULE.validate_freeze_record(record, self.contract)

    def test_manual_requires_passes_for_both_themes_at_each_width_and_language(self) -> None:
        record = MODULE.manual_template(self.contract, self.identity)
        self.assertEqual(len(record["results"]), 16)
        with self.assertRaisesRegex(MODULE.ProductAcceptanceError, "manual profiles awaiting a pass"):
            MODULE.validate_manual(record, self.contract, self.identity)
        for row in record["results"]:
            row["result"] = "pass"
        MODULE.validate_manual(record, self.contract, self.identity)
        record["results"].pop()
        with self.assertRaisesRegex(MODULE.ProductAcceptanceError, "each required profile exactly once"):
            MODULE.validate_manual(record, self.contract, self.identity)

    def test_manual_evidence_rejects_evidence_from_another_candidate(self) -> None:
        record = MODULE.manual_template(self.contract, self.identity)
        record["candidate_commit_sha"] = "c" * 40
        with self.assertRaisesRegex(MODULE.ProductAcceptanceError, "candidate_commit_sha does not match"):
            MODULE.validate_manual(record, self.contract, self.identity)

    def test_browser_evidence_rejects_an_expected_failure_as_a_pass(self) -> None:
        scenario = self.contract["browser"]["scenarios"]["access_and_accounting"]
        report = {
            "errors": [],
            "stats": {"unexpected": 0, "flaky": 0, "skipped": 0},
            "suites": [
                {
                    "specs": [
                        {
                            "file": scenario["file"],
                            "title": scenario["title"],
                            "tests": [
                                {"status": "expected", "expectedStatus": "failed", "results": [{"status": "failed"}]}
                            ],
                        }
                    ]
                }
            ],
        }
        with self.assertRaisesRegex(MODULE.ProductAcceptanceError, "required browser case did not pass"):
            MODULE.browser_results(self.contract, report)
