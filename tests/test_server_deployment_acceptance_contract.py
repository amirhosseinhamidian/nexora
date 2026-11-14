from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_server_deployment_acceptance_contract",
    ROOT / "scripts/verify_server_deployment_acceptance.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load server deployment acceptance verifier")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


class ServerDeploymentAcceptanceContractTests(unittest.TestCase):
    def test_contract_and_prerequisite_are_valid(self) -> None:
        VERIFY.validate_p2_12_prerequisite()
        VERIFY.validate_contract(VERIFY.load_contract())
        VERIFY.validate_files_and_markers()

    def test_public_network_exposure_is_rejected(self) -> None:
        contract = copy.deepcopy(VERIFY.load_contract())
        contract["deployment"]["public_network_exposure"] = True
        with self.assertRaisesRegex(VERIFY.ServerDeploymentAcceptanceContractError, "public exposure"):
            VERIFY.validate_contract(contract)

    def test_runtime_copy_cannot_become_off_host(self) -> None:
        contract = copy.deepcopy(VERIFY.load_contract())
        contract["backup_and_restore"]["runtime_copy_counts_as_off_host"] = True
        with self.assertRaisesRegex(VERIFY.ServerDeploymentAcceptanceContractError, "cannot count as off-host"):
            VERIFY.validate_contract(contract)

    def test_release_scope_cannot_expand_to_public_internet(self) -> None:
        contract = copy.deepcopy(VERIFY.load_contract())
        contract["acceptance_boundary"]["public_internet_production_readiness_claimed"] = True
        with self.assertRaisesRegex(VERIFY.ServerDeploymentAcceptanceContractError, "public readiness"):
            VERIFY.validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
