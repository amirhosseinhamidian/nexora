from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_platform_shell", ROOT / "scripts/verify_platform_shell.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P4-02 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PlatformShellContractTests(unittest.TestCase):
    def test_candidate_routes_and_prerequisite_are_valid(self) -> None:
        contract = MODULE.load_contract()
        MODULE.validate_prerequisite()
        MODULE.validate_contract(contract)
        MODULE.validate_runtime_markers(contract)

    def test_required_route_cannot_be_removed(self) -> None:
        contract = MODULE.load_contract()
        contract["routes"].remove("/{locale}/journal")
        with self.assertRaisesRegex(MODULE.PlatformShellContractError, "workspace route drift"):
            MODULE.validate_contract(contract)

    def test_persian_sidebar_cannot_move_left(self) -> None:
        contract = MODULE.load_contract()
        contract["navigation"]["desktop_sidebar_edge"]["fa"] = "left"
        with self.assertRaisesRegex(MODULE.PlatformShellContractError, "desktop sidebar direction drift"):
            MODULE.validate_contract(contract)

    def test_onboarding_cannot_open_before_freeze(self) -> None:
        contract = MODULE.load_contract()
        contract["transition"]["next_allowed_stage"] = "NEX-P4-03"
        with self.assertRaisesRegex(MODULE.PlatformShellContractError, "stage transition drift"):
            MODULE.validate_contract(contract)

    def test_freeze_record_is_valid(self) -> None:
        MODULE.validate_freeze_record(MODULE.load_freeze_record(), MODULE.load_contract())

    def test_freeze_rejects_ci_for_another_commit(self) -> None:
        record = MODULE.load_freeze_record()
        record["github_actions"]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PlatformShellContractError, "CI head SHA drift"):
            MODULE.validate_freeze_record(record, MODULE.load_contract())

    def test_freeze_requires_successful_web_and_browser_checks(self) -> None:
        record = MODULE.load_freeze_record()
        record["github_actions"]["jobs"]["platform-shell-web"]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.PlatformShellContractError, "CI job did not succeed"):
            MODULE.validate_freeze_record(record, MODULE.load_contract())

    def test_freeze_opens_only_p4_03(self) -> None:
        record = MODULE.load_freeze_record()
        record["next_allowed_stage"] = "NEX-P4-04"
        with self.assertRaisesRegex(MODULE.PlatformShellContractError, "post-Freeze stage drift"):
            MODULE.validate_freeze_record(record, MODULE.load_contract())


if __name__ == "__main__":
    unittest.main()
