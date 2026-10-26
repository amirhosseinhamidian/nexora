#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-single-owner-identity-runtime.json"
FREEZE_PATH = ROOT / "artifacts/p1-06/single-owner-identity-runtime-freeze.json"


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


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _json(path)


def _validate_workflow(
    workflow: object,
    *,
    label: str,
    run_id: int,
    expected_jobs: dict[str, tuple[int, str]],
    candidate_sha: str,
) -> None:
    _require(isinstance(workflow, dict), f"{label} workflow evidence must be an object")
    _require(workflow.get("run_id") == run_id, f"{label} run ID drift")
    _require(workflow.get("head_sha") == candidate_sha, f"{label} workflow head SHA drift")
    _require(workflow.get("event") == "push", f"{label} workflow must be a push run")
    _require(workflow.get("attempt") == 1, f"{label} workflow attempt drift")
    _require(workflow.get("conclusion") == "success", f"{label} workflow did not succeed")
    jobs = workflow.get("jobs")
    _require(isinstance(jobs, dict), f"{label} jobs must be an object")
    _require(set(jobs) == set(expected_jobs), f"{label} job inventory mismatch")
    for job_name, (job_id, displayed_name) in expected_jobs.items():
        job = jobs[job_name]
        _require(isinstance(job, dict), f"{label}/{job_name} must be an object")
        _require(job.get("job_id") == job_id, f"{label}/{job_name} job ID drift")
        _require(job.get("name") == displayed_name, f"{label}/{job_name} name drift")
        _require(job.get("conclusion") == "success", f"{label}/{job_name} did not succeed")


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
        "artifacts/p1-06/single-owner-identity-runtime-freeze.json",
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
    for marker in (
        "NEX-P1-06",
        "وضعیت: **Frozen**",
        "20261026_0003",
        "WebAuthn",
        "e7ea5484aaac6a9b2a60e25282044ad4c9649e20",
        "40322981155",
        "NEX-P1-ACCEPTANCE",
    ):
        _require(marker in document, f"document marker missing: {marker}")
    adr = (ROOT / "docs/adr/0020-passkey-session-and-private-runtime.md").read_text(encoding="utf-8")
    for marker in ("Status: **Frozen by NEX-P1-06**", "## Decision", "## Consequences"):
        _require(marker in adr, f"ADR marker missing: {marker}")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(
        record.get("schema_version") == "nexora-single-owner-identity-runtime-freeze-v1",
        "invalid freeze schema",
    )
    _require(record.get("decision_id") == "NEX-P1-06", "invalid freeze decision")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "invalid freeze repository")
    candidate_sha = record.get("candidate_commit_sha")
    _require(candidate_sha == "e7ea5484aaac6a9b2a60e25282044ad4c9649e20", "candidate SHA drift")
    _require(
        record.get("candidate_commit_message") == "feat(nexora): implement P1-06 single-owner identity runtime",
        "candidate commit message drift",
    )

    actions = record.get("github_actions")
    _validate_workflow(
        actions,
        label="single-owner identity runtime",
        run_id=40322981155,
        expected_jobs={
            "identity_contract": (121572380968, "identity-contract"),
            "backend": (121572380612, "backend"),
            "postgresql_17": (121572380849, "postgresql-17"),
            "private_topology": (121572381078, "private-topology"),
        },
        candidate_sha=candidate_sha,
    )
    _require(actions.get("head_branch") == "feature/v0.1-foundation", "invalid GitHub Actions branch")
    required_markers = {
        "identity_contract": (
            "p1_05_prerequisite_passed",
            "identity_runtime_verifier_passed",
            "repository_contract_tests_passed",
        ),
        "backend": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "non_integration_tests_passed",
        ),
        "postgresql_17": (
            "private_dsn_fixture_created",
            "upgrade_head_passed",
            "identity_integration_tests_passed",
            "downgrade_base_passed",
            "rebuild_head_passed",
            "migration_drift_check_passed",
        ),
        "private_topology": ("compose_configuration_passed",),
    }
    for job_name, markers in required_markers.items():
        for marker in markers:
            _require(actions["jobs"][job_name].get(marker) is True, f"{job_name} did not confirm {marker}")

    regression = record.get("regression_workflows")
    _require(isinstance(regression, dict), "regression workflow evidence must be an object")
    expected_regression = {
        "postgresql_schema": (
            40322981040,
            {
                "backend": (121572380183, "backend"),
                "database_contract": (121572380780, "database-contract"),
                "postgresql_17": (121572380799, "postgresql-17"),
            },
        ),
        "durable_jobs_outbox": (
            40322981125,
            {
                "postgresql_17": (121572380712, "postgresql-17"),
                "backend": (121572380950, "backend"),
                "durable_contract": (121572380978, "durable-contract"),
            },
        ),
        "contracts": (
            40322981168,
            {
                "security_boundary": (121572380883, "security-boundary"),
                "technical_baseline": (121572381342, "technical-baseline"),
                "phase_zero_acceptance": (121572381343, "phase-zero-acceptance"),
                "scope_contract": (121572381380, "scope-contract"),
                "integration_contract": (121572381685, "integration-contract"),
            },
        ),
        "runtime_foundation": (
            40322981197,
            {
                "backend": (121572380611, "backend"),
                "foundation_contract": (121572380923, "foundation-contract"),
                "web": (121572381221, "web"),
            },
        ),
        "trd_bot_adapter": (
            40322981241,
            {
                "adapter_contract": (121572380650, "adapter-contract"),
                "backend": (121572381437, "backend"),
            },
        ),
        "application_composition": (
            40322981384,
            {
                "composition_contract": (121572381413, "composition-contract"),
                "backend": (121572381958, "backend"),
            },
        ),
    }
    _require(set(regression) == set(expected_regression), "regression workflow inventory mismatch")
    for label, (run_id, jobs) in expected_regression.items():
        _validate_workflow(
            regression[label],
            label=label,
            run_id=run_id,
            expected_jobs=jobs,
            candidate_sha=candidate_sha,
        )

    contract_evidence = record.get("single_owner_identity_runtime_contract")
    _require(isinstance(contract_evidence, dict), "identity contract evidence must be an object")
    _require(contract_evidence.get("schema_version") == contract.get("schema_version"), "contract schema mismatch")
    _require(contract_evidence.get("checksum") == canonical_checksum(contract), "contract checksum mismatch")

    prerequisite = record.get("durable_jobs_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-05 freeze prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-05", "invalid P1-05 freeze prerequisite")
    _require(prerequisite.get("frozen") is True, "P1-05 freeze prerequisite is not frozen")
    p1_05_record = _json(ROOT / "artifacts/p1-05/durable-jobs-outbox-freeze.json")
    _require(
        prerequisite.get("freeze_record_checksum") == canonical_checksum(p1_05_record),
        "P1-05 freeze record checksum mismatch",
    )

    _require(record.get("recorded_on") == "2026-10-26", "invalid freeze record date")
    _require(record.get("frozen") is True, "P1-06 is not frozen")
    _require(
        record.get("single_owner_identity_runtime_complete") is True,
        "single-owner identity runtime is incomplete",
    )
    _require(
        record.get("private_single_host_topology_validated") is True,
        "private topology validation is missing",
    )
    for key in (
        "production_readiness_claimed",
        "public_internet_profile",
        "live_execution_capability",
        "wallet_capability",
        "autonomous_ai_execution",
    ):
        _require(record.get(key) is False, f"freeze record cannot enable {key}")
    _require(record.get("next_allowed_stage") == "NEX-P1-ACCEPTANCE", "invalid post-freeze next stage")


def main() -> int:
    validate_frozen_durable_jobs()
    contract = load_contract()
    validate_contract(contract)
    validate_files()
    validate_documents()
    freeze_record = load_freeze_record()
    validate_freeze_record(freeze_record, contract)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print(f"candidate_commit_sha={freeze_record['candidate_commit_sha']}")
    print("NEX_P1_05_PREREQUISITE=PASS")
    print("NEX_P1_06_SINGLE_OWNER_IDENTITY_RUNTIME=PASS")
    print("NEX_P1_06_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
