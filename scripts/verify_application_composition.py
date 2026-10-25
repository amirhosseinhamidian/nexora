#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-application-composition.json"

EXPECTED_ENVIRONMENT_VARIABLES = [
    "NEXORA_ENVIRONMENT",
    "NEXORA_DEPLOYMENT_PROFILE",
    "NEXORA_LOG_LEVEL",
    "NEXORA_DEFAULT_LOCALE",
    "NEXORA_DEFAULT_THEME",
    "NEXORA_API_HOST",
    "NEXORA_API_PORT",
]


class ApplicationCompositionError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ApplicationCompositionError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_frozen_runtime_foundation() -> None:
    path = ROOT / "scripts/verify_runtime_foundation.py"
    spec = importlib.util.spec_from_file_location("verify_runtime_foundation", path)
    if spec is None or spec.loader is None:
        raise ApplicationCompositionError("unable to load frozen P1-01 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_phase_zero()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_files(contract)
    module.validate_documents()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-application-composition-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P1-02", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-25", "invalid decision date")
    _require(contract.get("status") == "candidate", "P1-02 must remain candidate")

    prerequisite = contract.get("runtime_foundation_prerequisite")
    _require(isinstance(prerequisite, dict), "runtime foundation prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-01", "invalid runtime foundation prerequisite")
    _require(prerequisite.get("frozen") is True, "runtime foundation prerequisite is not frozen")
    _require(
        prerequisite.get("freeze_commit_sha") == "618907b0bc9c5f57e2e72f8d2c666a7f5b6b3266",
        "runtime foundation freeze commit drift",
    )
    freeze = _json(ROOT / prerequisite["freeze_record_path"])
    _require(
        canonical_checksum(freeze) == prerequisite.get("freeze_record_checksum"),
        "runtime foundation freeze checksum drift",
    )

    delivery = contract.get("delivery")
    _require(isinstance(delivery, dict), "delivery must be an object")
    for key in (
        "typed_runtime_configuration_delivered",
        "explicit_application_composition_delivered",
        "shared_api_worker_configuration_delivered",
        "configuration_fingerprint_delivered",
    ):
        _require(delivery.get(key) is True, f"P1-02 must deliver {key}")
    for key in (
        "production_readiness_claimed",
        "database_runtime_delivered",
        "authentication_runtime_delivered",
        "trd_bot_runtime_integration_delivered",
        "durable_worker_delivered",
    ):
        _require(delivery.get(key) is False, f"P1-02 cannot claim {key}")

    configuration = contract.get("configuration")
    _require(isinstance(configuration, dict), "configuration must be an object")
    _require(
        configuration.get("schema_version") == "nexora-runtime-configuration-v1",
        "runtime configuration schema drift",
    )
    _require(configuration.get("source") == "process_environment", "configuration source drift")
    for key in (
        "dotenv_auto_load",
        "secret_values_accepted",
    ):
        _require(configuration.get(key) is False, f"configuration boundary requires false: {key}")
    for key in (
        "immutable_after_load",
        "unknown_prefixed_variables_rejected",
        "empty_values_rejected",
    ):
        _require(configuration.get(key) is True, f"configuration boundary requires true: {key}")
    _require(
        configuration.get("allowed_environment_variables") == EXPECTED_ENVIRONMENT_VARIABLES,
        "environment variable inventory drift",
    )
    _require(configuration.get("forbidden_deployment_profile") == "public_internet", "public profile must be forbidden")
    _require(
        configuration.get("fingerprint_algorithm") == "sha256_canonical_json",
        "configuration fingerprint drift",
    )
    _require(
        configuration.get("default_fingerprint")
        == "5d4f9f7b6a1b7e1d8ab7af749136afff0b9e4de419d05f34a47497e68818ea04",
        "default configuration fingerprint drift",
    )

    composition = contract.get("composition")
    _require(isinstance(composition, dict), "composition must be an object")
    for key in (
        "api_and_worker_share_loader",
        "api_uses_injected_container",
        "worker_check_is_side_effect_free",
    ):
        _require(composition.get(key) is True, f"composition requires {key}")
    for key in (
        "global_service_locator",
        "database_adapter_registered",
        "authentication_adapter_registered",
        "trd_bot_adapter_registered",
        "durable_job_adapter_registered",
    ):
        _require(composition.get(key) is False, f"P1-02 forbids {key}")

    observability = contract.get("observability_boundary")
    _require(isinstance(observability, dict), "observability boundary must be an object")
    _require(observability.get("liveness_endpoint") == "/health/live", "liveness endpoint drift")
    _require(observability.get("liveness_response_unchanged") is True, "liveness response must remain stable")
    _require(observability.get("configuration_values_logged") is False, "configuration values cannot be logged")
    _require(observability.get("secret_values_logged") is False, "secret values cannot be logged")
    _require(
        observability.get("production_readiness_endpoint_claimed") is False,
        "P1-02 cannot claim a production readiness endpoint",
    )

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and len(security) == 7, "security inventory drift")
    for key, value in security.items():
        _require(value is False, f"forbidden capability enabled: {key}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_freeze") is True, "P1-02 is not ready for freeze")
    _require(transition.get("next_allowed_stage") == "NEX-P1-02-FREEZE", "next stage must be freeze")
    _require(transition.get("post_freeze_stage") == "NEX-P1-03", "post-freeze stage drift")


def validate_files(contract: dict[str, Any]) -> None:
    required = (
        "apps/server/src/nexora/config.py",
        "apps/server/src/nexora/composition.py",
        "apps/server/tests/test_config.py",
        "apps/server/tests/test_composition.py",
        ".github/workflows/application-composition.yml",
    )
    for relative in required:
        _require((ROOT / relative).is_file(), f"missing composition file: {relative}")

    config_source = (ROOT / "apps/server/src/nexora/config.py").read_text(encoding="utf-8")
    for marker in (
        "class RuntimeSettings(BaseModel)",
        'ConfigDict(extra="forbid", frozen=True)',
        "unknown Nexora environment variables",
        "sha256",
        "public_internet",
    ):
        _require(marker in config_source, f"configuration marker missing: {marker}")
    for forbidden in ("DATABASE_URL", "PASSWORD", "SECRET", "TOKEN", "CREDENTIAL"):
        _require(f'"NEXORA_{forbidden}"' not in config_source, f"secret-bearing configuration enabled: {forbidden}")

    composition_source = (ROOT / "apps/server/src/nexora/composition.py").read_text(encoding="utf-8")
    for marker in ("@dataclass(frozen=True, slots=True)", "class ApplicationContainer", "def compose_application"):
        _require(marker in composition_source, f"composition marker missing: {marker}")
    for forbidden in ("sqlalchemy", "psycopg", "trd_bot", "redis"):
        _require(forbidden not in composition_source.lower(), f"premature adapter in composition: {forbidden}")

    api = (ROOT / "apps/server/src/nexora/api.py").read_text(encoding="utf-8")
    worker = (ROOT / "apps/server/src/nexora/worker.py").read_text(encoding="utf-8")
    _require("compose_application(settings)" in api, "API does not use explicit composition")
    _require("load_settings()" in api, "API does not use shared settings")
    _require("compose_application(load_settings(environ))" in worker, "worker does not use shared composition")
    _require("worker execution is unavailable until NEX-P1-05" in worker, "worker boundary drift")

    env_lines = [
        line.split("=", 1)[0]
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    _require(env_lines == EXPECTED_ENVIRONMENT_VARIABLES, ".env.example inventory drift")
    _require(
        contract["configuration"]["allowed_environment_variables"] == env_lines,
        "contract and environment template disagree",
    )


def validate_documents() -> None:
    document = (ROOT / "docs/v0.1/06-application-composition-and-runtime-configuration.md").read_text(
        encoding="utf-8"
    )
    for marker in (
        "NEX-P1-02",
        "Candidate — Ready for Freeze",
        "fail-closed",
        "NEX_P1_02_APPLICATION_COMPOSITION=PASS",
        "NEX-P1-02-FREEZE",
    ):
        _require(marker in document, f"document marker missing: {marker}")
    adr = (ROOT / "docs/adr/0016-fail-closed-runtime-configuration-and-composition.md").read_text(encoding="utf-8")
    for marker in ("Status: Accepted by NEX-P1-02 candidate", "## Decision", "## Consequences"):
        _require(marker in adr, f"ADR marker missing: {marker}")
    workflow = (ROOT / ".github/workflows/application-composition.yml").read_text(encoding="utf-8")
    for marker in ("composition-contract:", "backend:", "verify_application_composition.py"):
        _require(marker in workflow, f"workflow marker missing: {marker}")


def main() -> int:
    validate_frozen_runtime_foundation()
    contract = load_contract()
    validate_contract(contract)
    validate_files(contract)
    validate_documents()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_01_PREREQUISITE=PASS")
    print("NEX_P1_02_APPLICATION_COMPOSITION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
