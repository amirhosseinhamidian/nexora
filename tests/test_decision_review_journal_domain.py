from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_decision_review_journal_domain",
    ROOT / "scripts/verify_decision_review_journal_domain.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-01 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DecisionReviewJournalDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_p3_00_prerequisite_is_valid(self) -> None:
        MODULE.validate_p3_00_prerequisite()

    def test_candidate_contract_and_repository_markers_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files_and_markers()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.CONTRACT_CHECKSUM)

    def test_p3_00_freeze_cannot_be_rebound(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["p3_00_prerequisite"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "Freeze commit drift"):
            MODULE.validate_contract(changed)

    def test_source_evidence_must_remain_immutable(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["source_evidence"]["immutable"] = False
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "immutable"):
            MODULE.validate_contract(changed)

    def test_unknown_schema_must_remain_quarantined(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["source_evidence"]["unknown_schema_action"] = "accept"
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "unknown schema"):
            MODULE.validate_contract(changed)

    def test_review_actions_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["human_review"]["actions"].remove("defer")
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "review actions"):
            MODULE.validate_contract(changed)

    def test_accept_cannot_create_order_intent(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["human_review"]["accept_creates_order_intent"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "OrderIntent"):
            MODULE.validate_contract(changed)

    def test_accept_cannot_post_transaction(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["human_review"]["accept_posts_transaction"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "posts a transaction"):
            MODULE.validate_contract(changed)

    def test_review_correction_must_preserve_lineage(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["human_review"]["correction"] = "in_place_edit"
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "correction lineage"):
            MODULE.validate_contract(changed)

    def test_owner_reason_codes_must_remain_namespaced(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["human_review"]["owner_reason_code_namespaces"]["reject"][0] = "stale_context"
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "reason namespace"):
            MODULE.validate_contract(changed)

    def test_what_if_cannot_submit_order(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["portfolio_impact"]["what_if_submits_order"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "submits an order"):
            MODULE.validate_contract(changed)

    def test_what_if_cannot_post_accounting_transaction(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["portfolio_impact"]["what_if_persists_accounting_transaction"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "posts a transaction"):
            MODULE.validate_contract(changed)

    def test_source_alert_must_remain_immutable(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["alert_domain"]["source_alert_immutable"] = False
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "source_alert_immutable"):
            MODULE.validate_contract(changed)

    def test_watchlist_cannot_create_trade_instruction(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["watchlist_domain"]["creates_trade_instruction"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "trade instruction"):
            MODULE.validate_contract(changed)

    def test_journal_must_remain_append_only(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["outcome_journal"]["append_only"] = False
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "append_only"):
            MODULE.validate_contract(changed)

    def test_journal_correction_must_preserve_history(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["outcome_journal"]["correction"] = "overwrite"
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "correction lineage"):
            MODULE.validate_contract(changed)

    def test_provider_sync_cannot_rewrite_human_note(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["outcome_journal"]["human_note_rewritten_by_provider_sync"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "rewrites human notes"):
            MODULE.validate_contract(changed)

    def test_ai_safe_export_cannot_include_credentials(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["export_policy"]["ai_safe_excludes"].remove("credentials")
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "AI-safe exclusions"):
            MODULE.validate_contract(changed)

    def test_public_export_download_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["export_policy"]["public_download"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "public export"):
            MODULE.validate_contract(changed)

    def test_p3_01_cannot_add_database_tables(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["persistence_boundary"]["database_tables_added_in_p3_01"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "boundary widened"):
            MODULE.validate_contract(changed)

    def test_trd_bot_0_3_0_cannot_be_marked_compatible(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["trd_bot_dependency"]["current_release_compatible"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "0.3.0"):
            MODULE.validate_contract(changed)

    def test_direct_trd_bot_database_access_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["trd_bot_dependency"]["direct_database_access"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "direct TRD Bot"):
            MODULE.validate_contract(changed)

    def test_server_gate_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["server_deployment_gate"]["removed"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "server gate removed"):
            MODULE.validate_contract(changed)

    def test_server_gate_cannot_be_bypassed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["server_deployment_gate"]["bypassed"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "server gate bypassed"):
            MODULE.validate_contract(changed)

    def test_forbidden_capability_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "forbidden capability"):
            MODULE.validate_contract(changed)

    def test_only_p3_01_freeze_is_opened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P3-02"
        with self.assertRaisesRegex(MODULE.DecisionReviewJournalDomainError, "next stage drift"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
