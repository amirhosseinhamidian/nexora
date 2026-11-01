from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_holdings_projection",
    ROOT / "scripts/verify_holdings_projection.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P2-05 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HoldingsProjectionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze = MODULE.load_freeze_record()

    def test_frozen_p2_04_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p2_04()

    def test_candidate_contract_and_runtime_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_runtime_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_freeze_record_is_valid(self) -> None:
        MODULE.validate_freeze_record(self.freeze, self.contract)
        MODULE.validate_freeze_workflow()

    def test_freeze_record_rejects_a_different_candidate(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.HoldingsProjectionContractError, "candidate SHA"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_a_failed_check(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["checks"][0]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.HoldingsProjectionContractError, "check evidence"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_opens_only_p2_06(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["next_allowed_stage"] = "NEX-P2-07"
        with self.assertRaisesRegex(MODULE.HoldingsProjectionContractError, "next stage"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_negative_holdings_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["projection_invariants"]["negative_holding_rejected"] = False
        with self.assertRaisesRegex(MODULE.HoldingsProjectionContractError, "negative_holding_rejected"):
            MODULE.validate_contract(changed)

    def test_transfer_cannot_become_a_disposal(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["projection_invariants"]["owned_account_transfer_is_not_disposal"] = False
        with self.assertRaisesRegex(MODULE.HoldingsProjectionContractError, "transfer_is_not_disposal"):
            MODULE.validate_contract(changed)

    def test_binary_float_cannot_enter_financial_calculation(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["projection_invariants"]["binary_float_forbidden"] = False
        with self.assertRaisesRegex(MODULE.HoldingsProjectionContractError, "binary_float_forbidden"):
            MODULE.validate_contract(changed)

    def test_missing_basis_cannot_be_invented(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["cost_basis_policy"]["missing_cost_evidence_cannot_be_invented"] = False
        with self.assertRaisesRegex(MODULE.HoldingsProjectionContractError, "missing_cost_evidence"):
            MODULE.validate_contract(changed)

    def test_owner_override_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime_api"]["owner_id_accepted_from_request"] = True
        with self.assertRaisesRegex(MODULE.HoldingsProjectionContractError, "owner override"):
            MODULE.validate_contract(changed)

    def test_valuation_cannot_enter_p2_05(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["valuation_included"] = True
        with self.assertRaisesRegex(MODULE.HoldingsProjectionContractError, "valuation_included"):
            MODULE.validate_contract(changed)

    def test_live_orders_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_orders"] = True
        with self.assertRaisesRegex(MODULE.HoldingsProjectionContractError, "live_orders"):
            MODULE.validate_contract(changed)

    def test_p2_06_cannot_open_before_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P2-06"
        with self.assertRaisesRegex(MODULE.HoldingsProjectionContractError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
