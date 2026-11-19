from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_phase_four_final_acceptance", ROOT / "scripts/verify_phase_four_final_acceptance.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P4-12 verifier")
acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)
product = acceptance.product


class PhaseFourFinalAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = acceptance.load_contract()
        self.p4_11 = product.load_json(product.FREEZE_PATH)
        self.identity = {"candidate_commit_sha": "a" * 40, "candidate_tree_sha": "b" * 40}
        self.ci = self._fixture_ci()

    def _fixture_ci(self) -> dict:
        workflows: dict = {}
        for index, gate in enumerate(self.contract["required_ci_gates"].values(), start=1):
            run = workflows.setdefault(
                gate["workflow"],
                {
                    "run_id": index,
                    "attempt": 1,
                    "head_sha": self.identity["candidate_commit_sha"],
                    "head_branch": self.contract["candidate_branch"],
                    "event": "push",
                    "conclusion": "success",
                    "jobs": {},
                },
            )
            run["jobs"][gate["job"]] = {
                "job_id": index,
                "head_sha": self.identity["candidate_commit_sha"],
                "run_attempt": 1,
                "conclusion": "success",
                "steps": dict.fromkeys(gate["steps"], "success"),
            }

        browser_workflow = self.contract["required_ci_gates"]["product_browser_journeys"]["workflow"]
        browser_run_id = workflows[browser_workflow]["run_id"]
        browser = {**self.p4_11["browser_evidence"], **self.identity}
        browser["github_actions"] = {"run_id": browser_run_id, "attempt": 1}
        browser.pop("record_checksum")
        browser["record_checksum"] = product.checksum(browser)
        return {
            "workflows": workflows,
            "browser_evidence": browser,
            "browser_artifact": {
                "name": "p4-11-browser-evidence",
                "artifact_id": 1,
                "run_id": browser_run_id,
                "digest": f"sha256:{'a' * 64}",
            },
        }

    def test_frozen_roadmap_and_prerequisites_are_valid(self) -> None:
        self.assertEqual(acceptance.validate_repository(self.contract), self.p4_11)

    def test_record_binds_passed_gates_and_preserves_deferred_items(self) -> None:
        record = acceptance.build_record(self.contract, self.p4_11, self.identity, self.ci)
        acceptance.validate_final_record(record, self.contract, self.p4_11)
        self.assertEqual(record["passed_gates"]["owner_visual_review"]["profile_count"], 16)
        self.assertEqual(record["deferred"], self.contract["deferred"])
        self.assertFalse(record["production_readiness_claimed"])
        record["production_readiness_claimed"] = True
        with self.assertRaisesRegex(product.ProductAcceptanceError, "record or checksum drift"):
            acceptance.validate_final_record(record, self.contract, self.p4_11)

    def test_ci_from_a_different_candidate_is_rejected(self) -> None:
        workflow = self.contract["required_ci_gates"]["product_browser_journeys"]["workflow"]
        self.ci["workflows"][workflow]["head_sha"] = "c" * 40
        with self.assertRaisesRegex(product.ProductAcceptanceError, "CI head SHA drift"):
            acceptance.build_record(self.contract, self.p4_11, self.identity, self.ci)

    def test_successful_workflow_cannot_substitute_for_migration_step(self) -> None:
        gate = self.contract["required_ci_gates"]["postgresql_migration_from_zero"]
        job = self.ci["workflows"][gate["workflow"]]["jobs"][gate["job"]]
        job["steps"]["Upgrade repository head from zero"] = "skipped"
        with self.assertRaisesRegex(product.ProductAcceptanceError, "Upgrade repository head from zero"):
            acceptance.build_record(self.contract, self.p4_11, self.identity, self.ci)
