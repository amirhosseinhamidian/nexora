from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_phase_three_export_coverage",
    ROOT / "scripts/verify_phase_three_export_coverage.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-11 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhaseThreeExportCoverageContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_prerequisite_contract_and_implementation_are_valid(self) -> None:
        MODULE.validate_prerequisite()
        MODULE.validate_contract(self.contract)
        MODULE.validate_implementation()
        MODULE.validate_workflow()

    def test_required_domain_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["required_domains"].remove("outcome_journal")
        with self.assertRaisesRegex(MODULE.PhaseThreeExportCoverageError, "domain coverage"):
            MODULE.validate_contract(changed)

    def test_ai_safe_cannot_drop_lineage(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["ai_safe"]["lineage_preserved"] = False
        with self.assertRaisesRegex(MODULE.PhaseThreeExportCoverageError, "lineage_preserved"):
            MODULE.validate_contract(changed)

    def test_partial_export_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["snapshot"]["partial_export_allowed"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeExportCoverageError, "partial export"):
            MODULE.validate_contract(changed)

    def test_public_download_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["public_download"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeExportCoverageError, "security"):
            MODULE.validate_contract(changed)

    def test_migration_cannot_be_added(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["persistence"]["new_migration_required"] = True
        with self.assertRaisesRegex(MODULE.PhaseThreeExportCoverageError, "new_migration_required"):
            MODULE.validate_contract(changed)

    def test_next_stage_cannot_skip_ui_integration(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage_after_ci_acceptance"] = "NEX-P3-13"
        with self.assertRaisesRegex(MODULE.PhaseThreeExportCoverageError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
