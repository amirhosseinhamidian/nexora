from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_monitoring_experience_ui", ROOT / "scripts/verify_monitoring_experience_ui.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P4-08 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MonitoringExperienceUiContractTests(unittest.TestCase):
    def test_candidate_routes_and_frozen_prerequisite_are_valid(self) -> None:
        contract = MODULE.load_contract()
        MODULE.validate_prerequisite()
        MODULE.validate_contract(contract)
        MODULE.validate_runtime_markers(contract)

    def test_external_notification_delivery_cannot_be_enabled(self) -> None:
        contract = MODULE.load_contract()
        contract["boundary"]["notification_delivery_enabled"] = True
        with self.assertRaisesRegex(MODULE.MonitoringExperienceUiContractError, "notification delivery"):
            MODULE.validate_contract(contract)
