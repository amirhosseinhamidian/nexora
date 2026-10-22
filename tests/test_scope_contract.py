from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_scope_contract",
    ROOT / "scripts" / "verify_scope_contract.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load scope verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ScopeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_contract_is_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_document()

    def test_contract_checksum_is_deterministic(self) -> None:
        reversed_contract = dict(reversed(list(self.contract.items())))
        self.assertEqual(
            MODULE.canonical_checksum(self.contract),
            MODULE.canonical_checksum(reversed_contract),
        )

    def test_live_trading_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["target"]["live_trading"] = True
        with self.assertRaisesRegex(MODULE.ScopeContractError, "live trading"):
            MODULE.validate_contract(changed)

    def test_direct_database_access_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["integration"]["direct_database_access"] = True
        with self.assertRaisesRegex(MODULE.ScopeContractError, "direct database"):
            MODULE.validate_contract(changed)

    def test_ai_execution_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["ai_ml"]["autonomous_execution_allowed"] = True
        with self.assertRaisesRegex(MODULE.ScopeContractError, "autonomous AI"):
            MODULE.validate_contract(changed)

    def test_export_formats_cannot_drop_parquet(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["export"]["formats"].remove("parquet")
        with self.assertRaisesRegex(MODULE.ScopeContractError, "formats"):
            MODULE.validate_contract(changed)

    def test_secret_export_denylist_is_required(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["export"]["forbidden_fields"].remove("api_secret")
        with self.assertRaisesRegex(MODULE.ScopeContractError, "denylist"):
            MODULE.validate_contract(changed)

    def test_next_stage_is_fixed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["next_allowed_stage"] = "NEX-P1-01"
        with self.assertRaisesRegex(MODULE.ScopeContractError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
