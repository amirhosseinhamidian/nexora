from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_phase_zero_acceptance",
    ROOT / "scripts" / "verify_phase_zero_acceptance.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load Phase 0 acceptance verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhaseZeroAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.matrix = MODULE.load_matrix()

    def test_frozen_p0_04_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_security_boundary()

    def test_phase_zero_candidate_is_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_matrix(self.matrix, self.contract)
        MODULE.validate_documents()

    def test_contract_checksum_is_deterministic(self) -> None:
        reversed_contract = dict(reversed(list(self.contract.items())))
        self.assertEqual(
            MODULE.canonical_checksum(self.contract),
            MODULE.canonical_checksum(reversed_contract),
        )

    def test_matrix_checksum_is_deterministic(self) -> None:
        reversed_matrix = dict(reversed(list(self.matrix.items())))
        self.assertEqual(
            MODULE.canonical_checksum(self.matrix),
            MODULE.canonical_checksum(reversed_matrix),
        )

    def test_prerequisite_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["frozen_prerequisites"].pop()
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "four frozen prerequisites"):
            MODULE.validate_contract(changed)

    def test_prerequisite_order_cannot_change(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["frozen_prerequisites"].reverse()
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "preserve the P0-01 through P0-04 order"):
            MODULE.validate_contract(changed)

    def test_prerequisite_must_be_frozen(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["frozen_prerequisites"][0]["frozen"] = False
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "prerequisite is not frozen"):
            MODULE.validate_contract(changed)

    def test_prerequisite_checksum_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["frozen_prerequisites"][2]["contract_checksum"] = "0" * 64
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "does not match frozen evidence"):
            MODULE.validate_contract(changed)

    def test_freeze_commit_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["frozen_prerequisites"][3]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "freeze_commit_sha"):
            MODULE.validate_contract(changed)

    def test_runtime_delivery_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase"]["runtime_delivered"] = True
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "runtime delivery"):
            MODULE.validate_contract(changed)

    def test_production_readiness_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["phase"]["production_readiness_claimed"] = True
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "production readiness"):
            MODULE.validate_contract(changed)

    def test_runtime_bootstrap_cannot_be_authorized_by_candidate(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["runtime_bootstrap_authorized"] = True
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "final freeze"):
            MODULE.validate_contract(changed)

    def test_next_stage_can_only_be_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P1-01"
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "next stage"):
            MODULE.validate_contract(changed)

    def test_unresolved_blocker_is_rejected(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["acceptance_summary"]["unresolved_phase_zero_blockers"] = 1
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "blockers remain"):
            MODULE.validate_contract(changed)

    def test_exact_pin_debt_cannot_be_falsely_closed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["debt_disposition"][0]["disposition"] = "closed"
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "invalid disposition"):
            MODULE.validate_contract(changed)

    def test_debt_owner_cannot_be_lost(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["debt_disposition"][4]["owner"] = "unknown"
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "debt owner drift"):
            MODULE.validate_contract(changed)

    def test_debt_cannot_remain_a_phase_zero_blocker(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["debt_disposition"][4]["blocking_phase_zero_freeze"] = True
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "unresolved Phase 0 blocker"):
            MODULE.validate_contract(changed)

    def test_live_order_capability_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["live_order_capability"] = True
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "live_order_capability"):
            MODULE.validate_contract(changed)

    def test_direct_trd_database_access_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["direct_trd_bot_database_access"] = True
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "direct_trd_bot_database_access"):
            MODULE.validate_contract(changed)

    def test_autonomous_ai_execution_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["security_boundary"]["autonomous_ai_execution"] = True
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "autonomous_ai_execution"):
            MODULE.validate_contract(changed)

    def test_requirement_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.matrix)
        changed["requirements"].pop()
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "twelve rows"):
            MODULE.validate_matrix(changed, self.contract)

    def test_requirement_ids_must_be_unique_and_ordered(self) -> None:
        changed = copy.deepcopy(self.matrix)
        changed["requirements"][1]["id"] = "NEX-P0-REQ-001"
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "unique and ordered"):
            MODULE.validate_matrix(changed, self.contract)

    def test_requirement_requires_an_owner(self) -> None:
        changed = copy.deepcopy(self.matrix)
        changed["requirements"][0]["owner"] = ""
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "owner is missing"):
            MODULE.validate_matrix(changed, self.contract)

    def test_requirement_requires_pass_status(self) -> None:
        changed = copy.deepcopy(self.matrix)
        changed["requirements"][0]["status"] = "pending"
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "not accepted"):
            MODULE.validate_matrix(changed, self.contract)

    def test_requirement_requires_durable_evidence(self) -> None:
        changed = copy.deepcopy(self.matrix)
        changed["requirements"][0]["evidence"] = []
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "durable evidence"):
            MODULE.validate_matrix(changed, self.contract)

    def test_missing_evidence_file_is_rejected(self) -> None:
        changed = copy.deepcopy(self.matrix)
        changed["requirements"][0]["evidence"][0] = "contracts/does-not-exist.json"
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "missing NEX-P0-REQ-001 evidence"):
            MODULE.validate_matrix(changed, self.contract)

    def test_evidence_path_cannot_escape_repository(self) -> None:
        changed = copy.deepcopy(self.matrix)
        changed["requirements"][0]["evidence"][0] = "../outside.json"
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "escapes the repository"):
            MODULE.validate_matrix(changed, self.contract)

    def test_requirement_requires_a_registered_verifier(self) -> None:
        changed = copy.deepcopy(self.matrix)
        changed["requirements"][0]["verifiers"] = ["trust_me"]
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "unknown verifier"):
            MODULE.validate_matrix(changed, self.contract)

    def test_every_phase_zero_decision_must_be_covered(self) -> None:
        changed = copy.deepcopy(self.matrix)
        for requirement in changed["requirements"]:
            requirement["source_decisions"] = [
                decision for decision in requirement["source_decisions"] if decision != "NEX-P0-05"
            ] or ["NEX-P0-04"]
        with self.assertRaisesRegex(MODULE.PhaseZeroAcceptanceError, "not every Phase 0 decision"):
            MODULE.validate_matrix(changed, self.contract)


if __name__ == "__main__":
    unittest.main()
