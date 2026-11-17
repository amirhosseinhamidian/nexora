from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_watchlists",
    ROOT / "scripts/verify_watchlists.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-09 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WatchlistContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_prerequisite_contract_and_implementation_are_valid(self) -> None:
        MODULE.validate_prerequisite()
        MODULE.validate_contract(self.contract)
        MODULE.validate_implementation()

    def test_item_kind_set_cannot_expand(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["watchlists"]["item_kinds"].append("order")
        with self.assertRaisesRegex(MODULE.WatchlistContractError, "item kind"):
            MODULE.validate_contract(changed)

    def test_optimistic_concurrency_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["watchlists"]["optimistic_concurrency"] = False
        with self.assertRaisesRegex(MODULE.WatchlistContractError, "optimistic"):
            MODULE.validate_contract(changed)

    def test_monitoring_preferences_cannot_become_unbounded(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["monitoring_preferences"]["bounded"] = False
        with self.assertRaisesRegex(MODULE.WatchlistContractError, "unbounded"):
            MODULE.validate_contract(changed)

    def test_provider_subscription_management_remains_deferred(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["monitoring_preferences"]["provider_subscription_management_enabled"] = True
        with self.assertRaisesRegex(MODULE.WatchlistContractError, "subscription"):
            MODULE.validate_contract(changed)

    def test_watchlist_cannot_create_trade_instruction(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["creates_trade_instruction"] = True
        with self.assertRaisesRegex(MODULE.WatchlistContractError, "security"):
            MODULE.validate_contract(changed)

    def test_nex_p3_03_remains_blocked(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["nex_p3_03_gate_opened"] = True
        with self.assertRaisesRegex(MODULE.WatchlistContractError, "prematurely"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
