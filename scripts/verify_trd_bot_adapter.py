#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-trd-bot-adapter.json"

EXPECTED_OPERATIONS = [
    "GET /capabilities",
    "GET /snapshots/{resource_type}",
    "GET /events",
    "GET /events/{event_id}",
    "POST /commands/decision-reviews",
    "POST /exports",
    "GET /exports/{export_id}",
    "GET /exports/{export_id}/manifest",
]
EXPECTED_COMMANDS = [
    "decision_review.accept.v1",
    "decision_review.reject.v1",
    "decision_review.defer.v1",
]
EXPECTED_SECURITY_BOUNDARY = {
    "direct_trd_bot_database_access",
    "shared_database",
    "exchange_credentials",
    "live_order_capability",
    "wallet_capability",
    "browser_service_token",
    "autonomous_ai_execution",
    "exactly_once_delivery_claim",
}


class TrdBotAdapterContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TrdBotAdapterContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_frozen_postgresql_schema() -> None:
    path = ROOT / "scripts/verify_postgresql_schema.py"
    spec = importlib.util.spec_from_file_location("verify_postgresql_schema", path)
    if spec is None or spec.loader is None:
        raise TrdBotAdapterContractError("unable to load frozen P1-03 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_application_composition()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_files(contract)
    module.validate_documents()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-trd-bot-adapter-v1", "invalid adapter schema")
    _require(contract.get("decision_id") == "NEX-P1-04", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-25", "invalid decision date")
    _require(contract.get("status") == "candidate", "P1-04 must remain candidate")

    prerequisite = contract.get("postgresql_schema_prerequisite")
    _require(isinstance(prerequisite, dict), "PostgreSQL prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-03", "invalid PostgreSQL prerequisite")
    _require(prerequisite.get("frozen") is True, "PostgreSQL prerequisite is not frozen")
    _require(
        prerequisite.get("freeze_commit_sha") == "519c193d911ff8b0e609c3b9be244a8034231c84",
        "PostgreSQL freeze commit drift",
    )
    record = _json(ROOT / prerequisite["freeze_record_path"])
    _require(
        canonical_checksum(record) == prerequisite.get("freeze_record_checksum"),
        "PostgreSQL freeze checksum drift",
    )

    delivery = contract.get("delivery")
    _require(isinstance(delivery, dict), "delivery must be an object")
    for key in (
        "typed_sync_client_delivered",
        "secure_file_configuration_delivered",
        "capability_negotiation_delivered",
        "strict_response_validation_delivered",
        "bounded_retry_policy_delivered",
        "all_eight_contract_operations_delivered",
    ):
        _require(delivery.get(key) is True, f"P1-04 must deliver {key}")
    for key in (
        "runtime_composition_registered",
        "durable_polling_delivered",
        "projection_persistence_delivered",
        "live_provider_smoke_claimed",
    ):
        _require(delivery.get(key) is False, f"P1-04 cannot claim {key}")

    interface = contract.get("interface")
    _require(isinstance(interface, dict), "interface must be an object")
    _require(interface.get("transport") == "https_json", "adapter transport drift")
    _require(interface.get("api_namespace") == "/api/v1/integration/nexora", "API namespace drift")
    _require(interface.get("operations") == EXPECTED_OPERATIONS, "operation inventory drift")
    _require(interface.get("page_limit_minimum") == 1, "minimum page limit drift")
    _require(interface.get("page_limit_maximum") == 500, "maximum page limit drift")
    _require(interface.get("redirects_followed") is False, "redirect following must remain disabled")
    _require(interface.get("response_content_type") == "application/json", "content type drift")

    compatibility = contract.get("compatibility")
    _require(isinstance(compatibility, dict), "compatibility must be an object")
    _require(compatibility.get("provider_release_range") == ">=0.3.1,<0.4.0", "provider range drift")
    _require(
        compatibility.get("provider_0_3_0_status") == "legacy_read_only_blocked",
        "TRD Bot 0.3.0 must remain blocked",
    )
    _require(compatibility.get("contract_versions") == ["nexora-trd-integration-v1"], "contract drift")
    _require(
        compatibility.get("event_envelopes") == ["trd-integration-event-envelope-v1"],
        "event envelope drift",
    )
    _require(
        compatibility.get("export_manifests") == ["nexora-export-manifest-v1"],
        "export manifest drift",
    )
    _require(
        compatibility.get("source_references") == ["nexora-source-reference-v1"],
        "source reference drift",
    )
    _require(compatibility.get("commands") == EXPECTED_COMMANDS, "command capability drift")
    for key in (
        "missing_or_unknown_capability_behavior",
        "provider_version_change_behavior",
        "precondition_failed_behavior",
        "expired_cursor_behavior",
    ):
        _require(isinstance(compatibility.get(key), str), f"compatibility behavior missing: {key}")

    retry = contract.get("retry_policy")
    _require(isinstance(retry, dict), "retry policy must be an object")
    _require(retry.get("maximum_attempts") == 4, "retry attempt budget drift")
    _require(retry.get("base_delay_ms") == 250, "retry base delay drift")
    _require(retry.get("maximum_delay_ms") == 4000, "retry maximum delay drift")
    _require(retry.get("jitter") == "full", "retry jitter drift")
    _require(retry.get("retryable_statuses") == [429, 502, 503, 504], "retryable statuses drift")
    _require(retry.get("post_retry_requires_idempotency_key") is True, "POST idempotency is required")
    _require(retry.get("respect_retry_after") is True, "Retry-After support is required")
    _require(retry.get("event_delivery") == "at_least_once", "delivery semantics drift")

    configuration = contract.get("configuration")
    _require(isinstance(configuration, dict), "configuration must be an object")
    _require(configuration.get("base_url_source") == "absolute_private_file", "base URL source drift")
    _require(configuration.get("token_source") == "absolute_private_file", "token source drift")
    _require(
        configuration.get("base_url_file_environment_variable") == "NEXORA_TRD_BOT_BASE_URL_FILE",
        "base URL file variable drift",
    )
    _require(
        configuration.get("token_file_environment_variable") == "NEXORA_TRD_BOT_TOKEN_FILE",
        "token file variable drift",
    )
    _require(configuration.get("symbolic_link_allowed") is False, "configuration symlinks are forbidden")
    _require(configuration.get("production_file_mode") == "0400", "production file mode drift")
    _require(configuration.get("production_transport") == "https", "production HTTPS is required")
    for key in ("credentials_logged", "credentials_exported", "credentials_sent_to_browser"):
        _require(configuration.get(key) is False, f"credential boundary requires false: {key}")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security boundary must be an object")
    _require(set(security) == EXPECTED_SECURITY_BOUNDARY, "security boundary inventory drift")
    for key, value in security.items():
        _require(value is False, f"forbidden capability enabled: {key}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_freeze") is True, "P1-04 is not ready for freeze")
    _require(transition.get("next_allowed_stage") == "NEX-P1-04-FREEZE", "next stage must be freeze")
    _require(transition.get("post_freeze_stage") == "NEX-P1-05", "post-freeze stage drift")


def validate_files() -> None:
    required = (
        "apps/server/src/nexora/adapters/trd_bot/__init__.py",
        "apps/server/src/nexora/adapters/trd_bot/client.py",
        "apps/server/src/nexora/adapters/trd_bot/config.py",
        "apps/server/src/nexora/adapters/trd_bot/errors.py",
        "apps/server/src/nexora/adapters/trd_bot/models.py",
        "apps/server/tests/test_trd_bot_client.py",
        "apps/server/tests/test_trd_bot_config.py",
        "apps/server/tests/test_trd_bot_models.py",
        ".github/workflows/trd-bot-adapter.yml",
    )
    for relative in required:
        _require((ROOT / relative).is_file(), f"missing adapter file: {relative}")

    client = (ROOT / "apps/server/src/nexora/adapters/trd_bot/client.py").read_text(encoding="utf-8")
    for marker in (
        'API_NAMESPACE: Final = "/api/v1/integration/nexora"',
        'CONTRACT_VERSION: Final = "nexora-trd-integration-v1"',
        "MAXIMUM_ATTEMPTS: Final = 4",
        "RETRYABLE_STATUSES: Final = frozenset({429, 502, 503, 504})",
        "follow_redirects=False",
        "CapabilityNegotiationRequired",
        "CursorExpiredError",
        'headers["Idempotency-Key"]',
    ):
        _require(marker in client, f"adapter client marker missing: {marker}")
    for forbidden in ("create_all", "live_order", "exchange_secret", "wallet_private_key"):
        _require(forbidden not in client, f"forbidden client capability present: {forbidden}")

    config = (ROOT / "apps/server/src/nexora/adapters/trd_bot/config.py").read_text(encoding="utf-8")
    for marker in (
        'TRD_BOT_BASE_URL_FILE_ENV: Final = "NEXORA_TRD_BOT_BASE_URL_FILE"',
        'TRD_BOT_TOKEN_FILE_ENV: Final = "NEXORA_TRD_BOT_TOKEN_FILE"',
        "path.is_absolute()",
        "stat.S_ISLNK",
        "mode != 0o400",
        "mode & 0o077",
        "SecretStr",
    ):
        _require(marker in config, f"secure adapter configuration marker missing: {marker}")
    for forbidden in ("dotenv", "NEXORA_TRD_BOT_TOKEN =", "print("):
        _require(forbidden not in config, f"unsafe adapter configuration marker present: {forbidden}")

    workflow = (ROOT / ".github/workflows/trd-bot-adapter.yml").read_text(encoding="utf-8")
    for marker in (
        "adapter-contract:",
        "backend:",
        "uv sync --frozen --python 3.13",
        'uv run pytest -m "not integration" -q',
    ):
        _require(marker in workflow, f"adapter workflow marker missing: {marker}")
    for forbidden in ("curl ", "wget ", "NEXORA_TRD_BOT_TOKEN:", "services:"):
        _require(forbidden not in workflow, f"adapter workflow has external dependency: {forbidden}")

    composition = (ROOT / "apps/server/src/nexora/composition.py").read_text(encoding="utf-8")
    _require("TrdBotClient" not in composition, "P1-04 cannot register the adapter in runtime composition")


def validate_documents() -> None:
    document = (ROOT / "docs/v0.1/08-versioned-trd-bot-adapter.md").read_text(encoding="utf-8")
    for marker in (
        "NEX-P1-04",
        "وضعیت: **Candidate**",
        "legacy_read_only_blocked",
        ">=0.3.1,<0.4.0",
        "NEX_P1_04_TRD_BOT_ADAPTER=PASS",
        "NEX-P1-04-FREEZE",
        "NEX-P1-05",
    ):
        _require(marker in document, f"document marker missing: {marker}")
    adr = (ROOT / "docs/adr/0018-fail-closed-versioned-trd-bot-adapter.md").read_text(encoding="utf-8")
    for marker in ("Status: Candidate for NEX-P1-04", "## Decision", "## Consequences"):
        _require(marker in adr, f"ADR marker missing: {marker}")


def main() -> int:
    validate_frozen_postgresql_schema()
    contract = load_contract()
    validate_contract(contract)
    validate_files()
    validate_documents()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_03_PREREQUISITE=PASS")
    print("NEX_P1_04_TRD_BOT_ADAPTER=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
