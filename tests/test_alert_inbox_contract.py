from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_alert_inbox",
    ROOT / "scripts/verify_alert_inbox.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-08 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AlertInboxContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_prerequisite_contract_and_implementation_are_valid(self) -> None:
        MODULE.validate_prerequisite()
        MODULE.validate_contract(self.contract)
        MODULE.validate_implementation()

    def test_owner_action_set_cannot_expand(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["owner_state"]["owner_actions"].append("execute")
        with self.assertRaisesRegex(MODULE.AlertInboxContractError, "action"):
            MODULE.validate_contract(changed)

    def test_source_alert_cannot_become_mutable(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["source_alerts"]["immutable"] = False
        with self.assertRaisesRegex(MODULE.AlertInboxContractError, "source alert"):
            MODULE.validate_contract(changed)

    def test_snooze_resume_time_remains_required(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["owner_state"]["snooze_until_required"] = False
        with self.assertRaisesRegex(MODULE.AlertInboxContractError, "snooze_until"):
            MODULE.validate_contract(changed)

    def test_notification_delivery_remains_deferred(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["notification_delivery"]["enabled"] = True
        with self.assertRaisesRegex(MODULE.AlertInboxContractError, "notification"):
            MODULE.validate_contract(changed)

    def test_alert_state_cannot_authorize_execution(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["acknowledgement_authorizes_execution"] = True
        with self.assertRaisesRegex(MODULE.AlertInboxContractError, "security"):
            MODULE.validate_contract(changed)

    def test_nex_p3_03_remains_blocked(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["nex_p3_03_gate_opened"] = True
        with self.assertRaisesRegex(MODULE.AlertInboxContractError, "prematurely"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
