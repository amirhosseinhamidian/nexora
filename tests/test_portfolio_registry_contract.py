from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_portfolio_registry",
    ROOT / "scripts/verify_portfolio_registry.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P2-02 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PortfolioRegistryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.freeze_record = MODULE.load_freeze_record()

    def test_frozen_p2_01_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_p2_01()

    def test_candidate_contract_and_runtime_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_runtime_markers()

    def test_freeze_record_and_workflow_are_valid(self) -> None:
        MODULE.validate_freeze_record(self.freeze_record, self.contract)
        MODULE.validate_freeze_workflow()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_owner_id_cannot_be_accepted_from_request(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime_api"]["owner_id_accepted_from_request"] = True
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "owner override"):
            MODULE.validate_contract(changed)

    def test_credentials_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["account_registry"]["credentials_supported"] = True
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "credentials"):
            MODULE.validate_contract(changed)

    def test_transaction_journal_cannot_enter_p2_02(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["transaction_journal_included"] = True
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "transaction_journal"):
            MODULE.validate_contract(changed)

    def test_physical_delete_cannot_be_exposed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["physical_delete_exposed"] = True
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "physical delete"):
            MODULE.validate_contract(changed)

    def test_lifecycle_row_version_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime_api"]["lifecycle_mutations_require_expected_row_version"] = False
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "row version"):
            MODULE.validate_contract(changed)

    def test_p2_03_cannot_open_before_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P2-03"
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "next stage"):
            MODULE.validate_contract(changed)

    def test_freeze_record_rejects_candidate_sha_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "candidate SHA drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_lineage_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["candidate_lineage"][1]["parent_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "candidate lineage drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_all_workflows(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["workflow_runs"].pop()
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "workflow run inventory drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_requires_all_checks(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["checks"].pop()
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "check inventory drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_failed_check(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["checks"][0]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "check evidence drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_rejects_contract_drift(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["portfolio_registry_contract"]["checksum"] = "0" * 64
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "contract evidence drift"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_cannot_claim_transaction_journal(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["transaction_journal_implemented"] = True
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "transaction journal"):
            MODULE.validate_freeze_record(changed, self.contract)

    def test_freeze_record_only_opens_p2_03(self) -> None:
        changed = copy.deepcopy(self.freeze_record)
        changed["next_allowed_stage"] = "NEX-P2-04"
        with self.assertRaisesRegex(MODULE.PortfolioRegistryContractError, "next stage drift"):
            MODULE.validate_freeze_record(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
