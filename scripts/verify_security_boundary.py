#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "nexora-v0.1-security-boundary.json"
SECURITY_BASE = ROOT / "contracts" / "security" / "v1"
DEPLOYMENT_PATH = SECURITY_BASE / "deployment-profiles.json"
HEADERS_PATH = SECURITY_BASE / "security-headers.json"
THREAT_MODEL_PATH = SECURITY_BASE / "threat-model.json"
AUDIT_SCHEMA_PATH = SECURITY_BASE / "audit-event.schema.json"
AUDIT_FIXTURE_PATH = SECURITY_BASE / "fixtures" / "security-audit-event.json"
DOCUMENT_PATH = ROOT / "docs" / "v0.1" / "03-security-identity-and-private-deployment-boundary.md"
ADR_PATHS = (
    ROOT / "docs" / "adr" / "0008-passkey-first-single-owner-identity.md",
    ROOT / "docs" / "adr" / "0009-opaque-server-side-sessions.md",
    ROOT / "docs" / "adr" / "0010-private-network-deployment-and-service-auth.md",
    ROOT / "docs" / "adr" / "0011-secret-and-encrypted-backup-boundary.md",
)
INTEGRATION_VERIFIER_PATH = ROOT / "scripts" / "verify_integration_contracts.py"

EXPECTED_AUDIT_EVENTS = {
    "identity.bootstrap.started",
    "identity.bootstrap.completed",
    "authentication.succeeded",
    "authentication.failed",
    "session.created",
    "session.rotated",
    "session.revoked",
    "credential.enrolled",
    "credential.revoked",
    "recovery.used",
    "service_token.rotated",
    "authorization.denied",
    "security.rate_limited",
    "backup.created",
    "backup.restored",
}
EXPECTED_SERVICE_SCOPES = {
    "source.snapshot.read",
    "source.event.read",
    "source.export.create",
    "source.export.read",
    "decision_review.write_paper_shadow",
}
SECRET_KEYS = {
    "password",
    "password_hash",
    "session_token",
    "session_cookie",
    "bearer_token",
    "service_token",
    "recovery_code",
    "bootstrap_token",
    "private_key",
    "passkey_challenge",
    "api_secret",
    "encryption_key",
    "raw_exchange_credential",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class SecurityBoundaryError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SecurityBoundaryError(message)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    _require(isinstance(payload, dict), f"{path.name} must contain a JSON object")
    return payload


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_deployment_profiles(path: Path = DEPLOYMENT_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_security_headers(path: Path = HEADERS_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_threat_model(path: Path = THREAT_MODEL_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_audit_schema(path: Path = AUDIT_SCHEMA_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_audit_fixture(path: Path = AUDIT_FIXTURE_PATH) -> dict[str, Any]:
    return _load_json(path)


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_integration_verifier() -> Any:
    spec = importlib.util.spec_from_file_location(
        "verify_integration_contracts",
        INTEGRATION_VERIFIER_PATH,
    )
    if spec is None or spec.loader is None:
        raise SecurityBoundaryError("unable to load the frozen P0-03 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_frozen_integration_contract() -> None:
    module = _load_integration_verifier()
    module.validate_frozen_baseline()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_matrix(module.load_matrix())
    module.validate_inventory(module.load_inventory())
    module.validate_openapi(module.load_openapi(), contract)
    module.validate_schemas(module.load_schemas())
    module.validate_fixtures(module.load_fixtures(), contract)
    module.validate_documents()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def _exact_set(payload: dict[str, Any], key: str, expected: set[Any]) -> None:
    value = payload.get(key)
    _require(isinstance(value, list), f"{key} must be an array")
    _require(set(value) == expected, f"{key} does not match the security boundary")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-security-boundary-v1", "invalid security boundary schema")
    _require(contract.get("decision_id") == "NEX-P0-04", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-24", "invalid decision date")
    _require(contract.get("status") == "candidate", "P0-04 contract must remain a candidate")

    product = contract.get("product")
    _require(isinstance(product, dict), "product must be an object")
    _require(product.get("name") == "Nexora", "invalid product name")
    _require(product.get("release_line") == "0.1.x", "invalid product release line")
    _require(product.get("edition") == "personal", "Nexora v0.1 must remain personal")
    _require(product.get("operating_model") == "single_owner", "Nexora v0.1 must remain single-owner")

    assurance = contract.get("assurance_model")
    _require(isinstance(assurance, dict), "assurance_model must be an object")
    _require(assurance.get("target") == "private_single_owner_financial_application", "invalid assurance target")
    _require(assurance.get("verification_baseline") == "owasp_asvs_5.0.0_level_2_selected_controls", "invalid ASVS baseline")
    _require(assurance.get("identity_guidance") == "nist_sp_800_63b_4", "invalid identity guidance")
    _require(assurance.get("default_decision") == "deny", "security decisions must deny by default")
    _require(assurance.get("runtime_delivered") is False, "P0-04 cannot claim runtime security delivery")

    artifacts = contract.get("artifacts")
    _require(isinstance(artifacts, dict), "artifacts must be an object")
    expected_artifacts = {
        "threat_model": "contracts/security/v1/threat-model.json",
        "deployment_profiles": "contracts/security/v1/deployment-profiles.json",
        "security_headers": "contracts/security/v1/security-headers.json",
        "audit_event_schema": "contracts/security/v1/audit-event.schema.json",
        "audit_event_fixture": "contracts/security/v1/fixtures/security-audit-event.json",
    }
    _require(artifacts == expected_artifacts, "security artifact inventory does not match")
    for relative in artifacts.values():
        _require((ROOT / relative).is_file(), f"missing security artifact: {relative}")

    identity = contract.get("identity")
    _require(isinstance(identity, dict), "identity must be an object")
    _exact_set(identity, "human_principals", {"owner"})
    _exact_set(identity, "service_principals", {"nexora_worker", "trd_bot_integration"})
    for key in ("self_registration", "invitations", "multi_user", "anonymous_application_access", "identity_provider_dependency"):
        _require(identity.get(key) is False, f"identity boundary forbids {key}")
    _require(identity.get("owner_account_count") == 1, "exactly one owner account is allowed")

    auth = contract.get("owner_authentication")
    _require(isinstance(auth, dict), "owner_authentication must be an object")
    _require(auth.get("primary_method") == "webauthn_passkey", "owner authentication must remain passkey-first")
    _require(auth.get("web_password_authentication") is False, "web password authentication is forbidden")
    _require(auth.get("minimum_registered_passkeys") == 1, "at least one passkey is required")
    _require(auth.get("second_passkey_recommended") is True, "a second passkey must remain recommended")
    _require(auth.get("user_verification") == "required", "WebAuthn user verification is required")
    _require(auth.get("resident_key") == "preferred", "resident key preference has drifted")
    _require(auth.get("attestation") == "none", "attestation must remain privacy-preserving")
    _require(set(auth.get("allowed_algorithms", [])) == {"ES256", "EdDSA"}, "WebAuthn algorithms are invalid")
    for key in ("rp_id_from_canonical_origin", "origin_exact_match", "challenge_single_use", "credential_counter_checked_when_supported"):
        _require(auth.get(key) is True, f"owner authentication requires {key}")
    _require(auth.get("challenge_entropy_bits") == 256, "challenge requires 256 bits of entropy")
    _require(auth.get("challenge_ttl_seconds") == 300, "challenge TTL must remain five minutes")
    _require(auth.get("credential_private_key_storage") == "authenticator_only", "credential private keys must remain in authenticators")
    _require("private_key" not in set(auth.get("credential_material_stored", [])), "private keys cannot be stored by Nexora")

    recovery = contract.get("bootstrap_and_recovery")
    _require(isinstance(recovery, dict), "bootstrap_and_recovery must be an object")
    _require(recovery.get("initial_owner_bootstrap") == "local_cli_one_time_token", "invalid owner bootstrap")
    _require(recovery.get("bootstrap_token_entropy_bits") == 256, "bootstrap token requires 256 bits")
    _require(recovery.get("bootstrap_token_ttl_seconds") == 600, "bootstrap token TTL must remain ten minutes")
    for key in ("bootstrap_token_single_use", "bootstrap_disabled_after_first_passkey", "recovery_codes_stored_as_digests", "recovery_codes_displayed_once", "recovery_requires_new_passkey_enrollment"):
        _require(recovery.get(key) is True, f"bootstrap and recovery requires {key}")
    _require(recovery.get("bootstrap_network_scope") == "loopback_or_private_network_only", "bootstrap network scope is too broad")
    _require(set(recovery.get("recovery_methods", [])) == {"single_use_recovery_codes", "local_operator_cli_reset"}, "recovery methods have drifted")
    _require(recovery.get("recovery_code_count") == 10, "ten recovery codes are required")
    _require(recovery.get("recovery_code_entropy_bits") == 128, "recovery code entropy is insufficient")
    _require(recovery.get("email_password_reset") is False, "email password reset is forbidden")
    _require(recovery.get("security_questions") is False, "security questions are forbidden")

    authorization = contract.get("authorization")
    _require(isinstance(authorization, dict), "authorization must be an object")
    _require(authorization.get("model") == "deny_by_default_role_and_scope", "authorization must deny by default")
    roles = authorization.get("roles")
    _require(isinstance(roles, dict) and set(roles) == {"owner", "nexora_worker", "trd_bot_integration"}, "authorization roles do not match")
    _require(set(roles["trd_bot_integration"]) == EXPECTED_SERVICE_SCOPES, "TRD Bot integration scopes do not match")
    _require(not any("live" in scope or "wallet" in scope for scopes in roles.values() for scope in scopes), "live or wallet authorization is forbidden")
    _require(authorization.get("recent_reauthentication_window_seconds") == 300, "recent reauthentication window is invalid")
    _require(authorization.get("live_execution_scope_exists") is False, "live execution scope is forbidden")

    session = contract.get("session")
    _require(isinstance(session, dict), "session must be an object")
    _require(session.get("model") == "opaque_server_side", "sessions must remain opaque and server-side")
    _require(session.get("token_entropy_bits") == 256, "session tokens require 256 bits")
    _require(session.get("token_storage") == "sha256_digest_only", "raw session tokens cannot be stored")
    cookie = session.get("cookie")
    _require(isinstance(cookie, dict), "session cookie must be an object")
    _require(cookie.get("name") == "__Host-nexora_session", "invalid session cookie name")
    for key in ("secure", "http_only"):
        _require(cookie.get(key) is True, f"session cookie requires {key}")
    _require(cookie.get("same_site") == "Strict", "session cookie must be SameSite Strict")
    _require(cookie.get("path") == "/", "session cookie path must be root")
    _require(cookie.get("domain_attribute") is False, "session cookie cannot have a Domain attribute")
    expected_session_values = {
        "idle_timeout_seconds": 1800,
        "absolute_timeout_seconds": 43200,
        "rotation_interval_seconds": 900,
        "rotation_grace_seconds": 30,
        "maximum_concurrent_sessions": 5,
    }
    for key, expected in expected_session_values.items():
        _require(session.get(key) == expected, f"invalid session policy: {key}")
    for key in ("rotate_after_authentication", "rotate_after_privilege_change", "revoke_on_credential_recovery", "revoke_all_supported", "logout_invalidates_server_state"):
        _require(session.get(key) is True, f"session policy requires {key}")
    _require(
        session.get("script_accessible_browser_storage") == "none",
        "script-accessible browser token storage is forbidden",
    )

    request = contract.get("request_protection")
    _require(isinstance(request, dict), "request_protection must be an object")
    _require(request.get("same_origin_web") is True, "web access must remain same-origin")
    _require(request.get("cors_allowed_origins") == [], "cross-origin CORS is forbidden")
    _require(request.get("csrf_strategy") == "synchronizer_token", "invalid CSRF strategy")
    _require(request.get("csrf_required_for_unsafe_methods") is True, "unsafe methods require CSRF protection")
    _require(request.get("origin_header_exact_match_for_unsafe_methods") is True, "unsafe methods require exact Origin checks")
    _require(request.get("content_types_for_mutations") == ["application/json"], "mutations must remain JSON-only")
    _require(request.get("request_body_size_limit_bytes") == 1048576, "request size limit has drifted")
    _require(request.get("authenticated_response_cache_control") == "no-store", "authenticated responses must not be cached")

    service = contract.get("trd_bot_service_authentication")
    _require(isinstance(service, dict), "trd_bot_service_authentication must be an object")
    _require(service.get("transport") == "tls_over_private_network", "TRD Bot transport must use private TLS")
    _require(service.get("credential_type") == "scoped_bearer_token", "invalid TRD Bot credential type")
    _require(service.get("token_entropy_bits") == 256, "service tokens require 256 bits")
    _require(service.get("token_sent_from_browser") is False, "service token cannot reach the browser")
    _require(service.get("token_storage_nexora") == "mounted_secret_file", "Nexora service token must use a mounted secret")
    _require(service.get("token_storage_trd_bot") == "hmac_sha256_digest_with_server_pepper", "TRD Bot must not store plaintext service tokens")
    for key in ("constant_time_verification", "contract_capability_negotiation_required", "revoke_supported", "per_request_correlation_id"):
        _require(service.get(key) is True, f"service authentication requires {key}")
    _require(set(service.get("scopes", [])) == EXPECTED_SERVICE_SCOPES, "service token scopes do not match")
    _require(service.get("maximum_token_age_days") == 90, "service token age is invalid")
    _require(service.get("rotation_overlap_hours") == 24, "service token rotation overlap is invalid")
    for key in ("live_order_scope_exists", "wallet_scope_exists", "exchange_credential_scope_exists"):
        _require(service.get(key) is False, f"service authentication forbids {key}")

    abuse = contract.get("abuse_protection")
    _require(isinstance(abuse, dict), "abuse_protection must be an object")
    _require(abuse.get("authentication_failures_per_window") == 5, "authentication failure limit has drifted")
    _require(abuse.get("authentication_window_seconds") == 900, "authentication rate window has drifted")
    _require(abuse.get("progressive_backoff") is True, "progressive backoff is required")
    _require(abuse.get("permanent_account_lockout") is False, "permanent owner lockout is forbidden")
    _require(abuse.get("generic_authentication_errors") is True, "generic authentication errors are required")
    _require(abuse.get("security_event_on_limit") is True, "rate limiting must emit a security event")

    deployment = contract.get("private_deployment")
    _require(isinstance(deployment, dict), "private_deployment must be an object")
    _require(deployment.get("production_profile") == "private_single_host", "invalid production profile")
    _require(deployment.get("public_internet_profile_supported") is False, "public internet deployment is forbidden")
    _require(deployment.get("remote_access") == "authenticated_private_overlay_network", "production requires private overlay access")
    _require(deployment.get("ingress") == "reverse_proxy_https_only", "production ingress must be HTTPS-only")
    _require(deployment.get("exposed_production_ports") == [443], "only port 443 may be exposed")
    for key in ("database_host_port_exposed", "worker_host_port_exposed", "production_debug_mode", "production_source_maps_public"):
        _require(deployment.get(key) is False, f"private deployment forbids {key}")
    for key in ("container_network_segmentation", "canonical_origin_allowlist_required", "trd_bot_endpoint_allowlisted", "host_or_provider_disk_encryption_required"):
        _require(deployment.get(key) is True, f"private deployment requires {key}")
    _require(deployment.get("tls_minimum_version") == "1.3", "TLS 1.3 minimum is required")
    _require(deployment.get("outbound_default") == "deny_except_declared_dependencies", "outbound network must deny by default")

    secrets = contract.get("secrets")
    _require(isinstance(secrets, dict), "secrets must be an object")
    _require(secrets.get("production_injection") == "read_only_mounted_secret_files", "invalid production secret injection")
    _require(secrets.get("development_injection") == "untracked_local_environment_file", "invalid development secret injection")
    for key in ("committed_secrets", "secrets_in_container_images", "secrets_in_database", "secrets_in_logs", "secrets_in_exports", "secrets_in_browser_bundle"):
        _require(secrets.get(key) is False, f"secret boundary forbids {key}")
    _require(secrets.get("minimum_random_secret_bits") == 256, "random secrets require 256 bits")
    _require(secrets.get("file_mode") == "0400", "secret file mode must remain 0400")
    for key in ("rotation_inventory_required", "ci_secret_scan_required", "redaction_required"):
        _require(secrets.get(key) is True, f"secret boundary requires {key}")

    audit = contract.get("audit")
    _require(isinstance(audit, dict), "audit must be an object")
    _require(audit.get("schema_version") == "nexora-security-audit-event-v1", "invalid audit schema version")
    _exact_set(audit, "event_types", EXPECTED_AUDIT_EVENTS)
    for key in ("append_only", "correlation_id_required", "actor_required", "outcome_required", "reason_code_required", "sensitive_values_forbidden"):
        _require(audit.get(key) is True, f"audit policy requires {key}")
    _require(audit.get("timestamps") == "UTC", "audit timestamps must use UTC")

    backup = contract.get("backup_and_restore")
    _require(isinstance(backup, dict), "backup_and_restore must be an object")
    for key in ("database_backup_encrypted", "artifact_backup_encrypted", "restore_requires_owner_presence", "restore_requires_recent_reauthentication", "service_tokens_rotated_after_restore", "sessions_revoked_after_restore", "restore_drill_required_before_release"):
        _require(backup.get(key) is True, f"backup policy requires {key}")
    _require(backup.get("encryption_profile") == "age_x25519_offline_recipient", "invalid backup encryption profile")
    _require(backup.get("private_key_online_storage") is False, "backup private key cannot be stored online")
    _require(backup.get("backup_manifest_checksums") == "sha256", "backup manifests require SHA-256")
    _require(backup.get("exports_are_backups") is False, "exports cannot be treated as backups")

    required_forbidden = {
        "public_self_registration",
        "multi_tenant_identity",
        "password_web_login",
        "email_password_reset",
        "browser_stored_bearer_token",
        "local_storage_session_token",
        "wildcard_cors",
        "public_database_port",
        "public_worker_port",
        "plaintext_service_token_storage",
        "secret_in_log_or_export",
        "public_internet_production_profile",
        "live_order_authorization",
        "wallet_authorization",
        "exchange_credential_authorization",
        "runtime_security_claim_before_implementation",
    }
    _require(required_forbidden <= set(contract.get("forbidden", [])), "forbidden security inventory is incomplete")
    _require(len(contract.get("deferred", [])) == 9, "deferred security inventory is incomplete")

    snapshot = contract.get("reference_snapshot")
    _require(isinstance(snapshot, dict), "reference_snapshot must be an object")
    _require(snapshot.get("checked_on") == "2026-10-24", "invalid reference snapshot date")
    sources = snapshot.get("sources")
    _require(isinstance(sources, list) and len(sources) == 5, "five official security references are required")
    _require(all(source.startswith(("https://asvs.owasp.org/", "https://cheatsheetseries.owasp.org/", "https://pages.nist.gov/")) for source in sources), "security references must use official sources")
    _require(contract.get("next_allowed_stage") == "NEX-P0-04-FREEZE", "next stage must be NEX-P0-04-FREEZE")


def validate_deployment_profiles(payload: dict[str, Any]) -> None:
    _require(payload.get("schema_version") == "nexora-deployment-profiles-v1", "invalid deployment profiles schema")
    _require(payload.get("decision_id") == "NEX-P0-04", "invalid deployment profiles decision")
    profiles = payload.get("profiles")
    _require(isinstance(profiles, list) and len(profiles) == 3, "three deployment profiles are required")
    by_id = {profile.get("id"): profile for profile in profiles}
    _require(set(by_id) == {"local_development", "private_single_host", "public_internet"}, "deployment profile IDs do not match")
    _require(by_id["local_development"].get("allowed") is True, "local development profile must be allowed")
    _require(by_id["local_development"].get("production_data") is False, "local development cannot use production data")
    _require(by_id["private_single_host"].get("allowed") is True, "private single-host profile must be allowed")
    _require(by_id["private_single_host"].get("tls") == "required_minimum_1.3", "private production requires TLS 1.3")
    _require(by_id["private_single_host"].get("database_exposure") == "container_network_only", "production database must remain internal")
    _require(by_id["public_internet"].get("allowed") is False, "public-internet profile is forbidden")
    topology = payload.get("private_single_host_topology")
    _require(isinstance(topology, dict), "private topology must be an object")
    _require(topology.get("only_exposed_port") == 443, "private topology exposes only port 443")
    _require(topology.get("postgresql_host_binding") is False, "PostgreSQL host binding is forbidden")
    _require(topology.get("worker_host_binding") is False, "worker host binding is forbidden")


def validate_security_headers(payload: dict[str, Any]) -> None:
    _require(payload.get("schema_version") == "nexora-security-headers-v1", "invalid security headers schema")
    _require(payload.get("decision_id") == "NEX-P0-04", "invalid security headers decision")
    headers = payload.get("headers")
    _require(isinstance(headers, dict), "security headers must be an object")
    expected = {
        "Content-Security-Policy",
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cross-Origin-Opener-Policy",
        "Cross-Origin-Resource-Policy",
        "Cache-Control",
    }
    _require(set(headers) == expected, "security header inventory does not match")
    csp = headers["Content-Security-Policy"]
    for directive in ("default-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "nonce-{runtime_nonce}"):
        _require(directive in csp, f"CSP is missing directive: {directive}")
    _require("'unsafe-inline'" not in csp, "CSP cannot allow unsafe-inline")
    _require("'unsafe-eval'" not in csp, "CSP cannot allow unsafe-eval")
    _require(headers["Strict-Transport-Security"] == "max-age=31536000", "invalid HSTS policy")
    _require(headers["Cache-Control"] == "no-store", "authenticated responses must use no-store")
    _require(set(payload.get("remove_response_headers", [])) == {"Server", "X-Powered-By"}, "response header removal list is invalid")
    _require(payload.get("csp_runtime_nonce_required") is True, "runtime CSP nonce is required")
    _require(payload.get("unsafe_inline_allowed") is False, "unsafe-inline must remain forbidden")
    _require(payload.get("unsafe_eval_allowed") is False, "unsafe-eval must remain forbidden")
    _require(payload.get("report_only_is_production_sufficient") is False, "report-only CSP is insufficient")


def validate_threat_model(payload: dict[str, Any]) -> None:
    _require(payload.get("schema_version") == "nexora-threat-model-v1", "invalid threat model schema")
    _require(payload.get("decision_id") == "NEX-P0-04", "invalid threat model decision")
    assets = payload.get("assets")
    boundaries = payload.get("trust_boundaries")
    _require(isinstance(assets, list) and len(assets) == 7 and len(set(assets)) == 7, "threat assets are incomplete")
    _require(isinstance(boundaries, list) and len(boundaries) == 5 and len(set(boundaries)) == 5, "trust boundaries are incomplete")
    threats = payload.get("threats")
    _require(isinstance(threats, list) and len(threats) == 10, "ten threat scenarios are required")
    expected_ids = {f"NEX-THREAT-{index:03d}" for index in range(1, 11)}
    _require({threat.get("id") for threat in threats} == expected_ids, "threat IDs do not match")
    for threat in threats:
        _require(threat.get("category") in {"spoofing", "tampering", "repudiation", "information_disclosure", "denial_of_service", "elevation_of_privilege"}, "invalid threat category")
        _require(threat.get("risk") in {"medium", "high", "critical"}, "invalid threat risk")
        _require(threat.get("residual_risk") in {"low", "medium"}, "invalid residual risk")
        _require(isinstance(threat.get("controls"), list) and len(threat["controls"]) >= 4, "each threat requires at least four controls")
        _require(bool(threat.get("scenario")), "each threat requires a scenario")
    non_goals = payload.get("explicit_non_goals")
    _require(isinstance(non_goals, list) and len(non_goals) == 5, "threat-model non-goals are incomplete")
    _require("live_trading_security" in non_goals, "live trading must remain outside the threat model")


def _timestamp(value: Any, label: str) -> None:
    _require(isinstance(value, str) and value.endswith("Z"), f"{label} must be a UTC timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SecurityBoundaryError(f"{label} is not a valid timestamp") from error


def _reject_secrets(value: Any, path: str = "audit fixture") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            _require(key.lower() not in SECRET_KEYS, f"secret-bearing audit key is forbidden: {path}.{key}")
            _reject_secrets(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secrets(nested, f"{path}[{index}]")


def validate_audit_contract(schema: dict[str, Any], fixture: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "invalid audit JSON Schema dialect")
    _require(schema.get("type") == "object", "audit schema root must be an object")
    _require(schema.get("additionalProperties") is False, "audit schema root must be closed")
    required = schema.get("required")
    _require(isinstance(required, list) and len(required) == 11, "audit schema required fields are incomplete")
    event_enum = schema.get("properties", {}).get("event_type", {}).get("enum", [])
    _require(set(event_enum) == EXPECTED_AUDIT_EVENTS, "audit schema event types do not match")
    _require(set(event_enum) == set(contract["audit"]["event_types"]), "audit schema and security contract disagree")

    _reject_secrets(fixture)
    expected_fields = {
        "schema_version",
        "event_id",
        "event_type",
        "occurred_at",
        "correlation_id",
        "actor",
        "target",
        "outcome",
        "reason_code",
        "network_context",
        "metadata",
    }
    _require(set(fixture) == expected_fields, "audit fixture fields do not match")
    _require(fixture.get("schema_version") == "nexora-security-audit-event-v1", "invalid audit fixture schema")
    _require(fixture.get("event_type") in EXPECTED_AUDIT_EVENTS, "invalid audit fixture event type")
    _require(isinstance(fixture.get("event_id"), str) and fixture["event_id"].startswith("sec_"), "invalid audit event ID")
    _timestamp(fixture.get("occurred_at"), "audit occurred_at")
    _require(isinstance(fixture.get("correlation_id"), str) and UUID.fullmatch(fixture["correlation_id"]) is not None, "invalid audit correlation ID")
    actor = fixture.get("actor")
    _require(isinstance(actor, dict) and set(actor) == {"type", "id"}, "invalid audit actor")
    _require(actor.get("type") in {"owner", "service", "system", "unknown"}, "invalid audit actor type")
    target = fixture.get("target")
    _require(isinstance(target, dict) and set(target) == {"type", "id"}, "invalid audit target")
    _require(fixture.get("outcome") in {"success", "failure", "denied"}, "invalid audit outcome")
    _require(re.fullmatch(r"^[A-Z][A-Z0-9_]{2,79}$", fixture.get("reason_code", "")) is not None, "invalid audit reason code")
    network = fixture.get("network_context")
    _require(isinstance(network, dict) and set(network) == {"source_class", "ip_address_hmac"}, "invalid audit network context")
    _require(network.get("source_class") in {"loopback", "private_overlay", "internal_service", "unknown"}, "invalid audit source class")
    digest = network.get("ip_address_hmac")
    _require(digest is None or (isinstance(digest, str) and SHA256.fullmatch(digest) is not None), "invalid IP address HMAC")


def validate_documents() -> None:
    text = DOCUMENT_PATH.read_text(encoding="utf-8")
    markers = (
        "NEX-P0-04",
        "وضعیت: **Candidate**",
        "WebAuthn passkey",
        "__Host-nexora_session",
        "SameSite=Strict",
        "synchronizer CSRF token",
        "private_single_host",
        "public_internet",
        "age X25519",
        "OWASP ASVS `5.0.0`",
        "NIST SP 800-63B-4",
        "NEX-P0-04-FREEZE",
        "NEX_P0_04_SECURITY_BOUNDARY=PASS",
    )
    missing = [marker for marker in markers if marker not in text]
    _require(not missing, f"security boundary document is missing markers: {missing}")
    for path in ADR_PATHS:
        _require(path.is_file(), f"missing ADR: {path.relative_to(ROOT)}")
        adr = path.read_text(encoding="utf-8")
        _require("Accepted candidate for NEX-P0-04" in adr, f"invalid ADR status: {path.name}")
        _require("## Decision" in adr, f"ADR decision is missing: {path.name}")
        _require("## Consequences" in adr, f"ADR consequences are missing: {path.name}")


def main() -> int:
    validate_frozen_integration_contract()
    contract = load_contract()
    validate_contract(contract)
    validate_deployment_profiles(load_deployment_profiles())
    validate_security_headers(load_security_headers())
    validate_threat_model(load_threat_model())
    validate_audit_contract(load_audit_schema(), load_audit_fixture(), contract)
    validate_documents()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P0_03_PREREQUISITE=PASS")
    print("NEX_P0_04_SECURITY_BOUNDARY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
