#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-single-owner-identity-runtime.json"


class IdentityRuntimeContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IdentityRuntimeContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_durable_jobs() -> None:
    path = ROOT / "scripts/verify_durable_jobs_outbox.py"
    spec = importlib.util.spec_from_file_location("verify_durable_jobs_outbox", path)
    if spec is None or spec.loader is None:
        raise IdentityRuntimeContractError("unable to load frozen P1-05 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_trd_bot_adapter()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_files()
    module.validate_documents()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-single-owner-identity-runtime-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P1-06", "invalid decision ID")
    _require(contract.get("status") == "candidate", "P1-06 must remain candidate")
    prerequisite = contract.get("durable_jobs_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-05 prerequisite must be an object")
    _require(prerequisite.get("frozen") is True, "P1-05 prerequisite is not frozen")
    _require(
        prerequisite.get("freeze_commit_sha") == "aaea7afcc7e6421a17f197f275d0beab853bc03e",
        "P1-05 freeze SHA drift",
    )
    freeze = _json(ROOT / prerequisite["freeze_record_path"])
    _require(canonical_checksum(freeze) == prerequisite.get("freeze_record_checksum"), "P1-05 freeze checksum drift")

    delivery = contract.get("delivery")
    _require(isinstance(delivery, dict), "delivery must be an object")
    _require(delivery.get("migration_revision") == "20261026_0003", "migration revision drift")
    for key in (
        "single_owner_identity_store",
        "cryptographic_webauthn_verifier",
        "opaque_server_side_sessions",
        "single_use_bootstrap_and_recovery",
        "scoped_service_token_metadata",
        "append_only_security_audit",
        "private_single_host_topology",
    ):
        _require(delivery.get(key) is True, f"P1-06 must deliver {key}")
    _require(delivery.get("production_readiness_claimed") is False, "candidate cannot claim production readiness")

    webauthn = contract.get("webauthn")
    _require(isinstance(webauthn, dict), "WebAuthn policy must be an object")
    _require(webauthn.get("library_version") == "2.7.0", "WebAuthn version drift")
    _require(webauthn.get("cbor2_compatibility_version") == "5.7.1", "CBOR compatibility pin drift")
    _require(set(webauthn.get("algorithms", [])) == {"ES256", "EdDSA"}, "WebAuthn algorithms drift")
    for key in ("challenge_single_use",):
        _require(webauthn.get(key) is True, f"WebAuthn requires {key}")
    _require(webauthn.get("private_key_persisted") is False, "passkey private key cannot be persisted")

    sessions = contract.get("sessions")
    _require(isinstance(sessions, dict), "session policy must be an object")
    expected = {
        "idle_timeout_seconds": 1800,
        "absolute_timeout_seconds": 43200,
        "rotation_interval_seconds": 900,
        "rotation_grace_seconds": 30,
        "maximum_concurrent_sessions": 5,
    }
    for key, value in expected.items():
        _require(sessions.get(key) == value, f"session policy drift: {key}")
    _require(sessions.get("raw_token_persisted") is False, "raw session tokens cannot be persisted")

    private_runtime = contract.get("private_runtime")
    _require(isinstance(private_runtime, dict), "private runtime policy must be an object")
    _require(
        set(private_runtime.get("base_loader_external_environment_allowlist", []))
        == {"NEXORA_DEV_DB_PASSWORD_FILE", "NEXORA_MIGRATION_DATABASE_DSN_FILE"},
        "base loader infrastructure environment allowlist drift",
    )

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security boundary must be an object")
    for key, value in security.items():
        _require(value is False, f"forbidden capability enabled: {key}")
    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_freeze") is True, "P1-06 is not ready for freeze")
    _require(transition.get("next_allowed_stage") == "NEX-P1-06-FREEZE", "next stage must be freeze")


def validate_files() -> None:
    required = (
        "alembic/versions/20261026_0003_single_owner_identity_runtime.py",
        "apps/server/src/nexora/identity.py",
        "apps/server/src/nexora/identity_service.py",
        "apps/server/src/nexora/identity_cli.py",
        "apps/server/src/nexora/security_config.py",
        "apps/server/src/nexora/adapters/postgresql/identity.py",
        "apps/server/tests/test_identity.py",
        "apps/server/tests/test_identity_integration.py",
        "infra/compose/private-single-host.yml",
        "infra/caddy/Caddyfile",
        "docs/adr/0020-passkey-session-and-private-runtime.md",
        "docs/v0.1/10-single-owner-identity-session-private-runtime.md",
        ".github/workflows/single-owner-identity-runtime.yml",
    )
    for relative in required:
        _require((ROOT / relative).is_file(), f"missing P1-06 file: {relative}")

    migration = (ROOT / required[0]).read_text(encoding="utf-8")
    for marker in (
        'revision: str = "20261026_0003"',
        'down_revision: str | None = "20261025_0002"',
        '"webauthn_credentials"',
        '"sessions"',
        '"security_audit_events"',
        "reject_security_audit_mutation",
        "def downgrade()",
    ):
        _require(marker in migration, f"migration marker missing: {marker}")

    identity = (ROOT / "apps/server/src/nexora/identity.py").read_text(encoding="utf-8")
    for marker in (
        "verify_registration_response",
        "require_user_verification=True",
        "COSEAlgorithmIdentifier.ECDSA_SHA_256",
        "COSEAlgorithmIdentifier.EDDSA",
        'SESSION_COOKIE_NAME: Final = "__Host-nexora_session"',
        "DenyAllWebAuthnVerifier",
    ):
        _require(marker in identity, f"identity marker missing: {marker}")
    repository = (ROOT / "apps/server/src/nexora/adapters/postgresql/identity.py").read_text(encoding="utf-8")
    for forbidden in ("password_hash", "live_order", "wallet_private_key", "exchange_api_secret"):
        _require(forbidden not in repository.lower(), f"forbidden identity capability: {forbidden}")

    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    _require('"webauthn==2.7.0"' in project, "WebAuthn dependency pin drift")
    _require('"cbor2==5.7.1"' in project, "Intel macOS CBOR compatibility pin drift")

    configuration = (ROOT / "apps/server/src/nexora/config.py").read_text(encoding="utf-8")
    for marker in (
        "INFRASTRUCTURE_ENVIRONMENT_VARIABLES",
        '"NEXORA_DEV_DB_PASSWORD_FILE"',
        '"NEXORA_MIGRATION_DATABASE_DSN_FILE"',
    ):
        _require(marker in configuration, f"infrastructure environment boundary missing: {marker}")

    topology = (ROOT / "infra/compose/private-single-host.yml").read_text(encoding="utf-8")
    _require("443:443" in topology, "private topology must expose TLS 443")
    for forbidden in ("5432:5432", "8000:8000", "3000:3000"):
        _require(forbidden not in topology, f"private topology exposes internal port: {forbidden}")


def validate_documents() -> None:
    document = (ROOT / "docs/v0.1/10-single-owner-identity-session-private-runtime.md").read_text(encoding="utf-8")
    for marker in ("NEX-P1-06", "Candidate", "20261026_0003", "WebAuthn", "NEX-P1-06-FREEZE"):
        _require(marker in document, f"document marker missing: {marker}")
    adr = (ROOT / "docs/adr/0020-passkey-session-and-private-runtime.md").read_text(encoding="utf-8")
    for marker in ("Status: **Candidate for NEX-P1-06**", "## Decision", "## Consequences"):
        _require(marker in adr, f"ADR marker missing: {marker}")


def main() -> int:
    validate_frozen_durable_jobs()
    contract = load_contract()
    validate_contract(contract)
    validate_files()
    validate_documents()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_05_PREREQUISITE=PASS")
    print("NEX_P1_06_SINGLE_OWNER_IDENTITY_RUNTIME=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
