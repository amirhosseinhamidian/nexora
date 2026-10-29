from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_phase_two_portfolio_domain",
    ROOT / "scripts/verify_phase_two_portfolio_domain.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P2-01 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhaseTwoPortfolioDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_phase_one_prerequisite_is_valid(self) -> None:
        MODULE.validate_phase_one_prerequisite()

    def test_candidate_contract_is_valid(self) -> None:
        MODULE.validate_contract(self.contract)

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_phase_one_freeze_commit_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["prerequisite"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "Freeze commit"):
            MODULE.validate_contract(changed)

    def test_financial_float_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["product_boundary"]["financial_float_allowed"] = True
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "financial float"):
            MODULE.validate_contract(changed)

    def test_portfolio_completion_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["product_boundary"]["portfolio_product_complete"] = True
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "product completion"):
            MODULE.validate_contract(changed)

    def test_transaction_journal_must_remain_immutable(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["domain_model"]["transaction_semantics"]["mutation"] = "update_allowed"
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "immutable"):
            MODULE.validate_contract(changed)

    def test_correction_lineage_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["domain_model"]["transaction_semantics"]["correction"] = "in_place_edit"
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "correction lineage"):
            MODULE.validate_contract(changed)

    def test_holdings_must_remain_derived(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["domain_model"]["projection_semantics"]["holdings_are_derived"] = False
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "holdings_are_derived"):
            MODULE.validate_contract(changed)

    def test_projections_must_remain_rebuildable(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["domain_model"]["projection_semantics"]["rebuildable_from_journal"] = False
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "rebuildable"):
            MODULE.validate_contract(changed)

    def test_transfer_basis_continuity_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["accounting_policy"]["transfer_between_owned_accounts"] = "disposal"
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "transfer policy"):
            MODULE.validate_contract(changed)

    def test_missing_price_must_remain_visible(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["valuation_policy"]["missing_price_must_be_visible"] = False
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "missing_price"):
            MODULE.validate_contract(changed)

    def test_import_dry_run_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["import_and_reconciliation"]["dry_run_required"] = False
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "dry_run_required"):
            MODULE.validate_contract(changed)

    def test_partial_import_publish_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["import_and_reconciliation"]["partial_publish_forbidden"] = False
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "partial import"):
            MODULE.validate_contract(changed)

    def test_parquet_cannot_be_removed_from_exports(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["export_policy"]["formats"].remove("parquet")
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "export format"):
            MODULE.validate_contract(changed)

    def test_ai_safe_export_cannot_include_credentials(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["export_policy"]["ai_safe_excludes"].remove("credentials")
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "credentials"):
            MODULE.validate_contract(changed)

    def test_public_export_download_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["export_policy"]["public_download"] = True
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "public export"):
            MODULE.validate_contract(changed)

    def test_trd_bot_0_3_0_cannot_be_marked_compatible(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["trd_bot_boundary"]["trd_bot_0_3_0_compatible"] = True
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "0.3.0"):
            MODULE.validate_contract(changed)

    def test_direct_trd_bot_database_access_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["trd_bot_boundary"]["direct_database_access"] = True
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "direct TRD Bot"):
            MODULE.validate_contract(changed)

    def test_live_orders_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_submission"] = True
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "live_order_submission"):
            MODULE.validate_contract(changed)

    def test_phase_two_stage_order_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase_two_roadmap"][1], changed["phase_two_roadmap"][2] = (
            changed["phase_two_roadmap"][2],
            changed["phase_two_roadmap"][1],
        )
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "stage order"):
            MODULE.validate_contract(changed)

    def test_only_p2_01_freeze_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P2-02"
        with self.assertRaisesRegex(MODULE.PhaseTwoPortfolioDomainError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
