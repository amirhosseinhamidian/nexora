from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_trd_bot_v031_integration_contract",
    ROOT / "scripts/verify_trd_bot_v031_integration_contract.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P3-02 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TrdBotV031IntegrationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.profile = MODULE.load_profile()

    def test_frozen_prerequisites_and_candidate_are_valid(self) -> None:
        MODULE.validate_prerequisites()
        MODULE.validate_profile(self.profile)
        MODULE.validate_contract(self.contract, self.profile)

    def test_profile_checksum_is_deterministic(self) -> None:
        reversed_profile = dict(reversed(list(self.profile.items())))
        self.assertEqual(
            MODULE.canonical_checksum(self.profile),
            MODULE.canonical_checksum(reversed_profile),
        )

    def test_trd_bot_0_3_0_cannot_be_compatible(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["provider_baseline"]["compatible"] = True
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "0.3.0 cannot be compatible"):
            MODULE.validate_contract(changed, self.profile)

    def test_provider_profile_cannot_accept_0_3_0(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["provider"]["release_0_3_0_compatible"] = True
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "0.3.0 cannot be compatible"):
            MODULE.validate_profile(changed)

    def test_service_token_cannot_be_delivered_to_browser(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["service_authentication"]["browser_delivery_allowed"] = True
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "browser_delivery_allowed"):
            MODULE.validate_profile(changed)

    def test_production_transport_cannot_be_downgraded(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["service_authentication"]["production_transport"] = "http"
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "transport weakened"):
            MODULE.validate_profile(changed)

    def test_snapshot_groups_cannot_overlap(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["snapshot_groups"]["alert"].append("candidate")
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "alert snapshot resources drift"):
            MODULE.validate_profile(changed)

    def test_snapshot_cursor_cannot_reset_silently(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["snapshot_protocol"]["silent_cursor_reset_allowed"] = True
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "silent snapshot cursor reset"):
            MODULE.validate_profile(changed)

    def test_exactly_once_delivery_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["event_feed"]["exactly_once_claimed"] = True
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "exactly-once"):
            MODULE.validate_profile(changed)

    def test_event_gap_detection_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["event_feed"]["gap_detection"] = "none"
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "gap detection"):
            MODULE.validate_profile(changed)

    def test_partial_resync_cannot_be_published(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["full_resync"]["partial_snapshot_publish_allowed"] = True
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "partial resync"):
            MODULE.validate_profile(changed)

    def test_review_command_cannot_authorize_execution(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["decision_review_command"]["execution_authorization"] = True
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "execution_authorization"):
            MODULE.validate_profile(changed)

    def test_review_source_of_truth_cannot_move_to_provider(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["decision_review_command"]["local_owner_review_source_of_truth"] = "trd_bot"
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "review ownership"):
            MODULE.validate_profile(changed)

    def test_local_review_expected_version_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["decision_review_command"]["optimistic_concurrency"]["expected_version_required_locally"] = False
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "expected version"):
            MODULE.validate_profile(changed)

    def test_partial_export_cannot_be_accepted(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["export_protocol"]["partial_export_accepted"] = True
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "partial export"):
            MODULE.validate_profile(changed)

    def test_real_provider_smoke_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["acceptance_smoke"]["real_provider_required"] = False
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "real provider smoke"):
            MODULE.validate_profile(changed)

    def test_p3_02_cannot_claim_runtime_implementation(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["implementation_boundary"]["nexora_runtime_behavior_added"] = True
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "implementation widened"):
            MODULE.validate_contract(changed, self.profile)

    def test_server_gate_cannot_be_bypassed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["server_deployment_gate"]["bypassed"] = True
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "server gate bypassed"):
            MODULE.validate_contract(changed, self.profile)

    def test_direct_database_access_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["direct_trd_bot_database_access"] = True
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "forbidden capability"):
            MODULE.validate_contract(changed, self.profile)

    def test_next_stage_is_only_p3_02_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P3-03"
        with self.assertRaisesRegex(MODULE.TrdBotV031IntegrationContractError, "next stage"):
            MODULE.validate_contract(changed, self.profile)


if __name__ == "__main__":
    unittest.main()
