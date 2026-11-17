from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_outcome_journal",
    ROOT / "scripts/verify_outcome_journal.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-10 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OutcomeJournalContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_prerequisite_contract_and_implementation_are_valid(self) -> None:
        MODULE.validate_prerequisite()
        MODULE.validate_contract(self.contract)
        MODULE.validate_implementation()

    def test_entry_kind_set_cannot_expand(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["journal"]["entry_kinds"].append("trade_instruction")
        with self.assertRaisesRegex(MODULE.OutcomeJournalContractError, "entry kind"):
            MODULE.validate_contract(changed)

    def test_append_only_boundary_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["journal"]["append_only"] = False
        with self.assertRaisesRegex(MODULE.OutcomeJournalContractError, "append_only"):
            MODULE.validate_contract(changed)

    def test_observed_outcome_lineage_remains_required(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["lineage"]["observed_outcome_source_lineage_required"] = False
        with self.assertRaisesRegex(MODULE.OutcomeJournalContractError, "lineage"):
            MODULE.validate_contract(changed)

    def test_update_and_delete_endpoints_remain_forbidden(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["api"]["delete_endpoint"] = True
        with self.assertRaisesRegex(MODULE.OutcomeJournalContractError, "delete"):
            MODULE.validate_contract(changed)

    def test_ai_generated_entries_remain_forbidden(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["ai_generated_entry_allowed"] = True
        with self.assertRaisesRegex(MODULE.OutcomeJournalContractError, "security"):
            MODULE.validate_contract(changed)

    def test_nex_p3_03_remains_blocked(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["nex_p3_03_gate_opened"] = True
        with self.assertRaisesRegex(MODULE.OutcomeJournalContractError, "prematurely"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
