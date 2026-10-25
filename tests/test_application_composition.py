from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_application_composition",
    ROOT / "scripts/verify_application_composition.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load application composition verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ApplicationCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def test_frozen_runtime_foundation_is_valid(self) -> None:
        MODULE.validate_frozen_runtime_foundation()

    def test_candidate_is_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_files(self.contract)
        MODULE.validate_documents()

    def test_checksum_is_deterministic(self) -> None:
        reversed_contract = dict(reversed(list(self.contract.items())))
        self.assertEqual(MODULE.canonical_checksum(self.contract), MODULE.canonical_checksum(reversed_contract))

    def test_runtime_foundation_freeze_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime_foundation_prerequisite"]["freeze_record_checksum"] = "0" * 64
        with self.assertRaisesRegex(MODULE.ApplicationCompositionError, "freeze checksum"):
            MODULE.validate_contract(changed)

    def test_unknown_variables_cannot_be_accepted(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["configuration"]["unknown_prefixed_variables_rejected"] = False
        with self.assertRaisesRegex(MODULE.ApplicationCompositionError, "unknown_prefixed"):
            MODULE.validate_contract(changed)

    def test_secret_values_cannot_be_accepted(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["configuration"]["secret_values_accepted"] = True
        with self.assertRaisesRegex(MODULE.ApplicationCompositionError, "secret_values"):
            MODULE.validate_contract(changed)

    def test_public_profile_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["configuration"]["forbidden_deployment_profile"] = "allowed"
        with self.assertRaisesRegex(MODULE.ApplicationCompositionError, "public profile"):
            MODULE.validate_contract(changed)

    def test_database_adapter_cannot_be_registered(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["composition"]["database_adapter_registered"] = True
        with self.assertRaisesRegex(MODULE.ApplicationCompositionError, "database_adapter"):
            MODULE.validate_contract(changed)

    def test_worker_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["delivery"]["durable_worker_delivered"] = True
        with self.assertRaisesRegex(MODULE.ApplicationCompositionError, "durable_worker"):
            MODULE.validate_contract(changed)

    def test_production_readiness_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["delivery"]["production_readiness_claimed"] = True
        with self.assertRaisesRegex(MODULE.ApplicationCompositionError, "production_readiness"):
            MODULE.validate_contract(changed)

    def test_next_stage_is_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "NEX-P1-03"
        with self.assertRaisesRegex(MODULE.ApplicationCompositionError, "next stage"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
