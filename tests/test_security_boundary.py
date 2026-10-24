from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_security_boundary",
    ROOT / "scripts" / "verify_security_boundary.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load security boundary verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SecurityBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.deployment = MODULE.load_deployment_profiles()
        self.headers = MODULE.load_security_headers()
        self.threat_model = MODULE.load_threat_model()
        self.audit_schema = MODULE.load_audit_schema()
        self.audit_fixture = MODULE.load_audit_fixture()

    def test_frozen_p0_03_prerequisite_is_valid(self) -> None:
        MODULE.validate_frozen_integration_contract()

    def test_candidate_security_boundary_is_valid(self) -> None:
        MODULE.validate_contract(self.contract)
        MODULE.validate_deployment_profiles(self.deployment)
        MODULE.validate_security_headers(self.headers)
        MODULE.validate_threat_model(self.threat_model)
        MODULE.validate_audit_contract(self.audit_schema, self.audit_fixture, self.contract)
        MODULE.validate_documents()

    def test_contract_checksum_is_deterministic(self) -> None:
        reversed_contract = dict(reversed(list(self.contract.items())))
        self.assertEqual(
            MODULE.canonical_checksum(self.contract),
            MODULE.canonical_checksum(reversed_contract),
        )

    def test_runtime_security_cannot_be_claimed_in_phase_zero(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["assurance_model"]["runtime_delivered"] = True
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "runtime security"):
            MODULE.validate_contract(changed)

    def test_second_human_account_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["identity"]["owner_account_count"] = 2
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "exactly one owner"):
            MODULE.validate_contract(changed)

    def test_self_registration_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["identity"]["self_registration"] = True
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "self_registration"):
            MODULE.validate_contract(changed)

    def test_web_password_authentication_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["owner_authentication"]["web_password_authentication"] = True
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "password authentication"):
            MODULE.validate_contract(changed)

    def test_webauthn_user_verification_cannot_be_weakened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["owner_authentication"]["user_verification"] = "preferred"
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "user verification"):
            MODULE.validate_contract(changed)

    def test_private_key_cannot_be_added_to_stored_credential_material(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["owner_authentication"]["credential_material_stored"].append("private_key")
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "private keys"):
            MODULE.validate_contract(changed)

    def test_recovery_codes_must_be_stored_as_digests(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["bootstrap_and_recovery"]["recovery_codes_stored_as_digests"] = False
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "recovery_codes_stored_as_digests"):
            MODULE.validate_contract(changed)

    def test_session_token_cannot_be_stored_in_the_browser(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["session"]["script_accessible_browser_storage"] = "local_storage"
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "browser token storage"):
            MODULE.validate_contract(changed)

    def test_session_cookie_cannot_drop_secure_flag(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["session"]["cookie"]["secure"] = False
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "cookie requires secure"):
            MODULE.validate_contract(changed)

    def test_csrf_protection_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["request_protection"]["csrf_required_for_unsafe_methods"] = False
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "CSRF protection"):
            MODULE.validate_contract(changed)

    def test_service_token_cannot_be_sent_to_the_browser(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["trd_bot_service_authentication"]["token_sent_from_browser"] = True
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "cannot reach the browser"):
            MODULE.validate_contract(changed)

    def test_live_order_scope_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["trd_bot_service_authentication"]["live_order_scope_exists"] = True
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "live_order_scope_exists"):
            MODULE.validate_contract(changed)

    def test_public_internet_deployment_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.deployment)
        changed["profiles"][2]["allowed"] = True
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "public-internet profile"):
            MODULE.validate_deployment_profiles(changed)

    def test_database_host_port_cannot_be_exposed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["private_deployment"]["database_host_port_exposed"] = True
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "database_host_port_exposed"):
            MODULE.validate_contract(changed)

    def test_secrets_cannot_be_written_to_logs(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["secrets"]["secrets_in_logs"] = True
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "secrets_in_logs"):
            MODULE.validate_contract(changed)

    def test_backup_encryption_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["backup_and_restore"]["database_backup_encrypted"] = False
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "database_backup_encrypted"):
            MODULE.validate_contract(changed)

    def test_csp_cannot_allow_unsafe_inline(self) -> None:
        changed = copy.deepcopy(self.headers)
        changed["headers"]["Content-Security-Policy"] += "; script-src 'unsafe-inline'"
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "unsafe-inline"):
            MODULE.validate_security_headers(changed)

    def test_threat_model_cannot_drop_a_scenario(self) -> None:
        changed = copy.deepcopy(self.threat_model)
        changed["threats"].pop()
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "ten threat scenarios"):
            MODULE.validate_threat_model(changed)

    def test_secret_bearing_audit_field_is_rejected(self) -> None:
        changed = copy.deepcopy(self.audit_fixture)
        changed["metadata"]["session_token"] = "must-not-exist"
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "secret-bearing audit key"):
            MODULE.validate_audit_contract(self.audit_schema, changed, self.contract)

    def test_audit_schema_must_remain_closed(self) -> None:
        changed = copy.deepcopy(self.audit_schema)
        changed["additionalProperties"] = True
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "root must be closed"):
            MODULE.validate_audit_contract(changed, self.audit_fixture, self.contract)

    def test_next_stage_is_only_p0_04_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["next_allowed_stage"] = "NEX-P1-01"
        with self.assertRaisesRegex(MODULE.SecurityBoundaryError, "P0-04-FREEZE"):
            MODULE.validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
