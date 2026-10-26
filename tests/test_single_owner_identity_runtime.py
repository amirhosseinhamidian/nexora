from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_single_owner_identity_runtime",
    ROOT / "scripts/verify_single_owner_identity_runtime.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SingleOwnerIdentityRuntimeContractTests(unittest.TestCase):
    def test_frozen_p1_05_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_durable_jobs()

    def test_candidate_contract_files_and_documents_are_valid(self) -> None:
        contract = MODULE.load_contract()
        MODULE.validate_contract(contract)
        MODULE.validate_files()
        MODULE.validate_documents()

    def test_live_capability_cannot_be_enabled(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["security_boundary"]["live_order_capability"] = True
        with self.assertRaises(MODULE.IdentityRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_session_token_cannot_be_marked_persisted(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["sessions"]["raw_token_persisted"] = True
        with self.assertRaises(MODULE.IdentityRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_passkey_private_key_cannot_be_persisted(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["webauthn"]["private_key_persisted"] = True
        with self.assertRaises(MODULE.IdentityRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_cbor_compatibility_pin_cannot_drift(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["webauthn"]["cbor2_compatibility_version"] = "6.1.5"
        with self.assertRaises(MODULE.IdentityRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_infrastructure_environment_allowlist_cannot_expand(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["private_runtime"]["base_loader_external_environment_allowlist"].append("NEXORA_DATABASE_URL")
        with self.assertRaises(MODULE.IdentityRuntimeContractError):
            MODULE.validate_contract(contract)

    def test_next_stage_is_only_freeze(self) -> None:
        contract = copy.deepcopy(MODULE.load_contract())
        contract["transition"]["next_allowed_stage"] = "NEX-P2-01"
        with self.assertRaises(MODULE.IdentityRuntimeContractError):
            MODULE.validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
