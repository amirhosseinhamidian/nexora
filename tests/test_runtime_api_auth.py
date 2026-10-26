from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_runtime_api_auth", ROOT / "scripts/verify_runtime_api_auth.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load P1-07 verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RuntimeApiAuthContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_phase_one_readiness_is_valid(self) -> None:
        MODULE.validate_frozen_phase_one_readiness()

    def test_candidate_contract_and_generated_outputs_are_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_generated_contracts()
        MODULE.validate_openapi()
        MODULE.validate_files_and_documents()

    def test_contract_checksum_is_deterministic(self) -> None:
        self.assertEqual(
            MODULE.canonical_checksum(self.contract), MODULE.canonical_checksum(copy.deepcopy(self.contract))
        )

    def test_unknown_schema_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.contract)
        candidate["schema_version"] = "nexora-runtime-api-auth-contract-v2"
        with self.assertRaisesRegex(MODULE.RuntimeApiAuthContractError, "invalid schema"):
            MODULE.validate_contract(candidate)

    def test_prerequisite_freeze_cannot_change(self) -> None:
        candidate = copy.deepcopy(self.contract)
        candidate["phase_one_readiness_prerequisite"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.RuntimeApiAuthContractError, "readiness freeze SHA drift"):
            MODULE.validate_contract(candidate)

    def test_closed_gap_inventory_cannot_change(self) -> None:
        candidate = copy.deepcopy(self.contract)
        candidate["closed_gaps"].pop()
        with self.assertRaisesRegex(MODULE.RuntimeApiAuthContractError, "gap inventory drift"):
            MODULE.validate_contract(candidate)

    def test_recent_reauthentication_cannot_be_weakened(self) -> None:
        candidate = copy.deepcopy(self.contract)
        candidate["authentication_lifecycle"]["recent_reauthentication_seconds"] = 3600
        with self.assertRaisesRegex(MODULE.RuntimeApiAuthContractError, "window drift"):
            MODULE.validate_contract(candidate)

    def test_runtime_operation_cannot_be_removed(self) -> None:
        candidate = copy.deepcopy(self.contract)
        candidate["operations"].pop()
        with self.assertRaisesRegex(MODULE.RuntimeApiAuthContractError, "operation inventory drift"):
            MODULE.validate_contract(candidate)

    def test_generated_checksum_cannot_change(self) -> None:
        candidate = copy.deepcopy(self.contract)
        candidate["contract_toolchain"]["contract_checksum"] = "0" * 64
        with self.assertRaisesRegex(MODULE.RuntimeApiAuthContractError, "runtime checksum drift"):
            MODULE.validate_contract(candidate)

    def test_forbidden_capability_cannot_be_enabled(self) -> None:
        candidate = copy.deepcopy(self.contract)
        candidate["security_boundary"]["live_execution_capability"] = True
        with self.assertRaisesRegex(MODULE.RuntimeApiAuthContractError, "forbidden capability enabled"):
            MODULE.validate_contract(candidate)

    def test_next_stage_must_be_freeze(self) -> None:
        candidate = copy.deepcopy(self.contract)
        candidate["transition"]["next_allowed_stage"] = "NEX-P1-08"
        with self.assertRaisesRegex(MODULE.RuntimeApiAuthContractError, "next stage must be freeze"):
            MODULE.validate_contract(candidate)


if __name__ == "__main__":
    unittest.main()
