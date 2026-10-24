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
BASE = ROOT / "contracts" / "integration" / "v1"
CONTRACT_PATH = BASE / "integration-contract.json"
MATRIX_PATH = BASE / "compatibility-matrix.json"
INVENTORY_PATH = BASE / "trd-bot-v0.3.0-inventory.json"
OPENAPI_PATH = BASE / "openapi.json"
SCHEMA_DIR = BASE / "schemas"
FIXTURE_DIR = BASE / "fixtures"
DOCUMENT_PATH = ROOT / "docs" / "v0.1" / "02-api-event-export-contracts-and-compatibility.md"
ADR_PATHS = (
    ROOT / "docs" / "adr" / "0005-dedicated-nexora-integration-boundary.md",
    ROOT / "docs" / "adr" / "0006-pollable-event-feed-at-least-once.md",
    ROOT / "docs" / "adr" / "0007-deterministic-export-bundles.md",
)
BASELINE_VERIFIER_PATH = ROOT / "scripts" / "verify_technical_baseline.py"

EXPECTED_OPERATIONS = {
    ("GET", "/api/v1/integration/nexora/capabilities", "getNexoraIntegrationCapabilities"),
    (
        "GET",
        "/api/v1/integration/nexora/snapshots/{resource_type}",
        "listNexoraSourceSnapshots",
    ),
    ("GET", "/api/v1/integration/nexora/events", "listNexoraIntegrationEvents"),
    (
        "GET",
        "/api/v1/integration/nexora/events/{event_id}",
        "getNexoraIntegrationEvent",
    ),
    (
        "POST",
        "/api/v1/integration/nexora/commands/decision-reviews",
        "submitNexoraDecisionReview",
    ),
    ("POST", "/api/v1/integration/nexora/exports", "createNexoraSourceExport"),
    (
        "GET",
        "/api/v1/integration/nexora/exports/{export_id}",
        "getNexoraSourceExport",
    ),
    (
        "GET",
        "/api/v1/integration/nexora/exports/{export_id}/manifest",
        "getNexoraSourceExportManifest",
    ),
}
EXPECTED_EVENT_TYPES = {
    "market_context.assessed.v1",
    "decision.evaluation.completed.v1",
    "candidate.state.changed.v1",
    "risk_gate.completed.v1",
    "portfolio_intelligence.completed.v1",
    "alert.published.v1",
    "alert.lifecycle.changed.v1",
    "simulation.position.opened.v1",
    "simulation.position.updated.v1",
    "simulation.position.closed.v1",
    "outcome.recorded.v1",
}
EXPECTED_COMMAND_TYPES = {
    "decision_review.accept.v1",
    "decision_review.reject.v1",
    "decision_review.defer.v1",
}
EXPECTED_RESOURCES = {
    "market_context",
    "decision_evaluation",
    "candidate",
    "risk_gate",
    "portfolio_intelligence",
    "alert",
    "alert_outcome",
    "paper_shadow_portfolio",
    "paper_shadow_position",
    "simulation_outcome",
}
FORBIDDEN_SECRET_KEYS = {
    "password",
    "password_hash",
    "session_token",
    "refresh_token",
    "api_secret",
    "encryption_key",
    "raw_exchange_credential",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SOURCE_CHECKSUM = re.compile(r"^sha256:[0-9a-f]{64}$")
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class IntegrationContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IntegrationContractError(message)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    _require(isinstance(payload, dict), f"{path.name} must contain a JSON object")
    return payload


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_matrix(path: Path = MATRIX_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_inventory(path: Path = INVENTORY_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_openapi(path: Path = OPENAPI_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_schemas() -> dict[str, dict[str, Any]]:
    return {path.name: _load_json(path) for path in sorted(SCHEMA_DIR.glob("*.schema.json"))}


def load_fixtures() -> dict[str, dict[str, Any]]:
    return {path.name: _load_json(path) for path in sorted(FIXTURE_DIR.glob("*.json"))}


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_baseline_verifier() -> Any:
    spec = importlib.util.spec_from_file_location(
        "verify_technical_baseline",
        BASELINE_VERIFIER_PATH,
    )
    if spec is None or spec.loader is None:
        raise IntegrationContractError("unable to load the P0-02 baseline verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_frozen_baseline() -> None:
    module = _load_baseline_verifier()
    module.validate_frozen_scope()
    contract = module.load_contract()
    freeze_record = module.load_freeze_record()
    module.validate_contract(contract)
    module.validate_documents()
    module.validate_freeze_record(freeze_record, contract)


def _exact_set(payload: dict[str, Any], key: str, expected: set[Any]) -> None:
    value = payload.get(key)
    _require(isinstance(value, list), f"{key} must be an array")
    _require(set(value) == expected, f"{key} does not match the integration contract")


def validate_contract(contract: dict[str, Any]) -> None:
    _require(
        contract.get("schema_version") == "nexora-trd-integration-contract-v1",
        "invalid integration contract schema",
    )
    _require(contract.get("decision_id") == "NEX-P0-03", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-22", "invalid decision date")
    _require(contract.get("status") == "candidate", "P0-03 contract must remain a candidate")

    provider = contract.get("provider")
    consumer = contract.get("consumer")
    _require(isinstance(provider, dict), "provider must be an object")
    _require(isinstance(consumer, dict), "consumer must be an object")
    _require(provider.get("product") == "TRD Bot", "invalid provider")
    _require(provider.get("release_line") == "0.3.x", "invalid provider release line")
    _require(
        provider.get("minimum_contract_release") == "0.3.1",
        "TRD Bot 0.3.1 must remain the minimum contract release",
    )
    _require(consumer.get("product") == "Nexora", "invalid consumer")
    _require(consumer.get("release_line") == "0.1.x", "invalid consumer release line")
    _require(consumer.get("edition") == "personal", "Nexora v0.1 must remain personal")

    details = contract.get("contract")
    _require(isinstance(details, dict), "contract details must be an object")
    expected_details = {
        "name": "nexora-trd-integration-v1",
        "api_namespace": "/api/v1/integration/nexora",
        "openapi_version": "3.1.0",
        "json_schema_dialect": "https://json-schema.org/draft/2020-12/schema",
        "canonical_timezone": "UTC",
        "delivery_semantics": "at_least_once",
        "ordering_scope": "per_aggregate",
        "unknown_schema_behavior": "fail_closed",
    }
    for key, expected in expected_details.items():
        _require(details.get(key) == expected, f"invalid integration contract {key}")

    operations = contract.get("operations")
    _require(isinstance(operations, list), "operations must be an array")
    actual_operations = {
        (entry.get("method"), entry.get("path"), entry.get("operation_id"))
        for entry in operations
        if isinstance(entry, dict)
    }
    _require(actual_operations == EXPECTED_OPERATIONS, "operation inventory does not match")
    _require(len(operations) == len(EXPECTED_OPERATIONS), "operation IDs must be unique")
    for operation in operations:
        expected_retry = "idempotent_command" if operation["method"] == "POST" else "safe"
        _require(operation.get("retry_class") == expected_retry, "invalid operation retry class")

    request_headers = contract.get("required_request_headers")
    _require(isinstance(request_headers, dict), "required_request_headers must be an object")
    _require(
        set(request_headers.get("all_requests", [])) == {"Accept", "X-Correlation-ID"},
        "common request headers are incomplete",
    )
    _require(
        set(request_headers.get("commands", [])) == {"Content-Type", "Idempotency-Key"},
        "command request headers are incomplete",
    )
    _require(
        set(contract.get("required_response_headers", []))
        == {"Content-Type", "X-Correlation-ID", "X-TRD-Bot-Version", "X-Contract-Version"},
        "response headers are incomplete",
    )
    _exact_set(contract, "source_resources", EXPECTED_RESOURCES)
    _exact_set(contract, "event_types", EXPECTED_EVENT_TYPES)
    _exact_set(contract, "command_types", EXPECTED_COMMAND_TYPES)

    feed = contract.get("event_feed")
    _require(isinstance(feed, dict), "event_feed must be an object")
    _require(feed.get("cursor") == "opaque_stable_cursor", "cursor must remain opaque")
    _require(feed.get("default_limit") == 100, "invalid default feed limit")
    _require(feed.get("maximum_limit") == 500, "invalid maximum feed limit")
    _require(feed.get("long_polling") is False, "long polling is not in the v1 contract")
    _require(feed.get("cursor_expiry_status") == 410, "expired cursors must return 410")
    _require(
        feed.get("cursor_expiry_action") == "full_snapshot_resync",
        "expired cursors must trigger full snapshot resync",
    )
    _require(
        set(feed.get("deduplication_keys", [])) == {"event_id", "idempotency_key"},
        "event deduplication keys are incomplete",
    )
    _require(feed.get("gap_detection") == "aggregate_version", "invalid gap detection")
    _require(feed.get("acknowledgement_required") is False, "pull feed must not require ack")

    retry = contract.get("retry_policy")
    _require(isinstance(retry, dict), "retry_policy must be an object")
    _require(retry.get("maximum_attempts") == 4, "invalid retry attempt limit")
    _require(retry.get("base_delay_ms") == 250, "invalid base retry delay")
    _require(retry.get("maximum_delay_ms") == 4000, "invalid maximum retry delay")
    _require(retry.get("jitter") == "full", "full jitter is required")
    _require(
        set(retry.get("retryable_statuses", [])) == {429, 502, 503, 504},
        "retryable status inventory is invalid",
    )
    _require(
        set(retry.get("non_retryable_statuses", []))
        == {400, 401, 403, 404, 409, 410, 412, 422},
        "non-retryable status inventory is invalid",
    )
    _require(
        retry.get("post_retry_requires_idempotency_key") is True,
        "POST retry requires an idempotency key",
    )
    _require(retry.get("respect_retry_after") is True, "Retry-After must be respected")

    failures = contract.get("failure_semantics")
    _require(isinstance(failures, dict), "failure_semantics must be an object")
    expected_failures = {
        "unknown_contract_version": "incompatible_fail_closed",
        "unknown_payload_schema": "quarantine_and_degrade",
        "checksum_mismatch": "reject_and_alert",
        "event_gap": "pause_projection_and_backfill",
        "cursor_expired": "full_snapshot_resync",
        "source_unavailable": "serve_last_verified_snapshot_as_stale",
        "partial_export": "reject_as_unsuccessful",
        "idempotency_conflict": "reject_without_replay",
        "timeout_after_command": "lookup_by_idempotency_key_before_retry",
    }
    _require(failures == expected_failures, "failure semantics have drifted")

    export = contract.get("export")
    _require(isinstance(export, dict), "export must be an object")
    _require(set(export.get("modes", [])) == {"full", "incremental", "selected"}, "invalid export modes")
    _require(
        set(export.get("formats", [])) == {"json", "jsonl", "csv", "parquet", "zip_bundle"},
        "invalid export formats",
    )
    _require(set(export.get("profiles", [])) == {"private", "ai_safe"}, "invalid export profiles")
    _require(export.get("accepted_completion_status") == "complete", "partial export cannot be accepted")
    _require(export.get("checksum_algorithm") == "sha256", "SHA-256 is required")
    _require(export.get("canonical_json") == "rfc8785", "RFC 8785 canonical JSON is required")
    _require(export.get("secret_fields_forbidden") is True, "secret fields must be forbidden")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict), "security_boundary must be an object")
    _require(
        security.get("authentication_mechanism_decision") == "NEX-P0-04",
        "authentication must remain deferred to NEX-P0-04",
    )
    _require(
        security.get("transport_security_decision") == "NEX-P0-04",
        "transport security must remain deferred to NEX-P0-04",
    )
    for key in ("direct_database_access", "exchange_credentials", "live_order_capability", "wallet_capability"):
        _require(security.get(key) is False, f"security boundary forbids {key}")
    _require(security.get("allowed_command_scope") == "paper_shadow_only", "command scope must remain Paper/Shadow")

    gaps = contract.get("provider_gaps")
    _require(isinstance(gaps, list) and len(gaps) == 4, "four blocking provider gaps are required")
    _require({gap.get("id") for gap in gaps} == {f"TRD-NEX-GAP-00{i}" for i in range(1, 5)}, "provider gap IDs are invalid")
    for gap in gaps:
        _require(gap.get("release") == "0.3.0", "provider gap release must be 0.3.0")
        _require(gap.get("required_release") == "0.3.1", "provider gaps must target 0.3.1")
        _require(gap.get("blocking") is True, "all provider gaps must remain blocking")

    required_forbidden = {
        "direct_trd_bot_database_access",
        "unversioned_payload_acceptance",
        "silent_cursor_reset",
        "exactly_once_delivery_claim",
        "retry_post_without_idempotency_key",
        "accept_partial_export",
        "export_secret_fields",
        "live_order_command",
        "wallet_command",
        "exchange_credential_command",
    }
    _require(required_forbidden <= set(contract.get("forbidden", [])), "forbidden capability inventory is incomplete")
    _require(contract.get("next_allowed_stage") == "NEX-P0-03-FREEZE", "next stage must be NEX-P0-03-FREEZE")


def validate_matrix(matrix: dict[str, Any]) -> None:
    _require(matrix.get("schema_version") == "nexora-trd-compatibility-matrix-v1", "invalid compatibility matrix schema")
    _require(matrix.get("decision_id") == "NEX-P0-03", "invalid matrix decision")
    _require(matrix.get("contract") == "nexora-trd-integration-v1", "invalid matrix contract")
    entries = matrix.get("entries")
    _require(isinstance(entries, list) and len(entries) == 4, "compatibility matrix requires four release ranges")
    by_release = {entry.get("provider_release"): entry for entry in entries}
    _require(set(by_release) == {"<0.3.0", "0.3.0", ">=0.3.1,<0.4.0", ">=0.4.0"}, "invalid provider release ranges")
    _require(by_release["0.3.0"].get("status") == "legacy_read_only_blocked", "TRD Bot 0.3.0 cannot be compatible")
    _require(
        by_release["0.3.0"].get("runtime_action") == "show_incompatible_and_do_not_sync",
        "TRD Bot 0.3.0 must not sync",
    )
    _require(by_release[">=0.3.1,<0.4.0"].get("status") == "compatible_if_capabilities_match", "0.3.1 compatibility must be negotiated")
    _require(by_release[">=0.4.0"].get("runtime_action") == "fail_closed", "unknown major/minor releases must fail closed")
    capabilities = matrix.get("required_capabilities")
    _require(isinstance(capabilities, dict), "required_capabilities must be an object")
    _require(capabilities.get("contract_versions") == ["nexora-trd-integration-v1"], "invalid required contract")
    _require(capabilities.get("event_envelopes") == ["trd-integration-event-envelope-v1"], "invalid event envelope capability")
    _require(capabilities.get("export_manifests") == ["nexora-export-manifest-v1"], "invalid export manifest capability")
    _require(capabilities.get("source_references") == ["nexora-source-reference-v1"], "invalid source reference capability")
    _require(set(capabilities.get("commands", [])) == EXPECTED_COMMAND_TYPES, "invalid command capabilities")
    negotiation = matrix.get("negotiation")
    _require(isinstance(negotiation, dict), "negotiation must be an object")
    _require(negotiation.get("endpoint") == "/api/v1/integration/nexora/capabilities", "invalid negotiation endpoint")
    _require(negotiation.get("recheck_on_412") is True, "HTTP 412 must recheck capabilities")
    _require(negotiation.get("missing_capability_behavior") == "fail_closed", "missing capabilities must fail closed")
    _require(negotiation.get("unknown_schema_behavior") == "fail_closed", "unknown schemas must fail closed")


def validate_inventory(inventory: dict[str, Any]) -> None:
    _require(inventory.get("schema_version") == "trd-bot-nexora-source-inventory-v1", "invalid provider inventory schema")
    _require(inventory.get("provider") == "TRD Bot", "invalid inventory provider")
    _require(inventory.get("provider_version") == "0.3.0", "inventory must describe TRD Bot 0.3.0")
    endpoints = inventory.get("read_endpoints")
    _require(isinstance(endpoints, list) and len(endpoints) == 22, "provider inventory must contain 22 read endpoints")
    _require(len(set(endpoints)) == len(endpoints), "provider endpoint inventory contains duplicates")
    _require(inventory.get("assessment") == "legacy_read_only_blocked", "provider assessment must remain blocked")
    _require(inventory.get("direct_database_fallback_allowed") is False, "direct database fallback is forbidden")
    limitations = inventory.get("observed_limitations")
    _require(isinstance(limitations, list) and len(limitations) == 6, "provider limitations are incomplete")


def _operation_parameters(operation: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for parameter in operation.get("parameters", []):
        if isinstance(parameter, dict) and isinstance(parameter.get("$ref"), str):
            result.add(parameter["$ref"])
        elif isinstance(parameter, dict) and isinstance(parameter.get("name"), str):
            result.add(parameter["name"])
    return result


def validate_openapi(openapi: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(openapi.get("openapi") == "3.1.0", "OpenAPI 3.1.0 is required")
    _require(openapi.get("x-nexora-contract") == "nexora-trd-integration-v1", "OpenAPI contract marker is invalid")
    _require(openapi.get("x-nexora-security-decision") == "NEX-P0-04", "OpenAPI security decision must remain deferred")
    paths = openapi.get("paths")
    _require(isinstance(paths, dict), "OpenAPI paths must be an object")
    actual: set[tuple[str, str, str]] = set()
    for path, path_item in paths.items():
        _require(isinstance(path_item, dict), f"invalid OpenAPI path item: {path}")
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            _require(isinstance(operation, dict), f"invalid OpenAPI operation: {path}")
            actual.add((method.upper(), path, operation.get("operationId")))
            parameters = _operation_parameters(operation)
            _require(
                "#/components/parameters/CorrelationId" in parameters,
                f"OpenAPI operation requires X-Correlation-ID: {path}",
            )
            if method.lower() == "post":
                _require(
                    "#/components/parameters/IdempotencyKey" in parameters,
                    f"OpenAPI POST requires Idempotency-Key: {path}",
                )
                _require(operation.get("requestBody", {}).get("required") is True, f"OpenAPI POST requires a body: {path}")
            responses = operation.get("responses")
            _require(isinstance(responses, dict), f"OpenAPI operation requires responses: {path}")
            success_codes = [code for code in responses if code.startswith("2")]
            _require(len(success_codes) == 1, f"OpenAPI operation requires one success response: {path}")
            success = responses[success_codes[0]]
            _require(isinstance(success, dict), f"invalid OpenAPI success response: {path}")
            _require("application/json" in success.get("content", {}), f"OpenAPI success response requires JSON: {path}")
            _require(
                set(success.get("headers", {}))
                == {"X-Correlation-ID", "X-TRD-Bot-Version", "X-Contract-Version"},
                f"OpenAPI success response headers are incomplete: {path}",
            )
    _require(actual == EXPECTED_OPERATIONS, "OpenAPI operation inventory does not match the contract")
    contract_operations = {
        (entry["method"], entry["path"], entry["operation_id"])
        for entry in contract["operations"]
    }
    _require(actual == contract_operations, "OpenAPI operations and contract operations disagree")
    serialized = json.dumps(openapi, sort_keys=True).lower()
    for forbidden in ("/orders", "/wallet", "exchange_credential", "live_order"):
        _require(forbidden not in serialized, f"OpenAPI exposes forbidden capability: {forbidden}")


def validate_schemas(schemas: dict[str, dict[str, Any]]) -> None:
    expected = {
        "source-reference.schema.json",
        "event-envelope.schema.json",
        "export-manifest.schema.json",
        "error-envelope.schema.json",
    }
    _require(set(schemas) == expected, "JSON Schema inventory does not match")
    for name, schema in schemas.items():
        _require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"invalid schema dialect: {name}")
        _require(schema.get("type") == "object", f"root schema must be an object: {name}")
        _require(schema.get("additionalProperties") is False, f"root schema must be closed: {name}")
        _require(isinstance(schema.get("required"), list) and schema["required"], f"schema requires explicit fields: {name}")
    event_enum = schemas["event-envelope.schema.json"]["properties"]["event_type"]["enum"]
    _require(set(event_enum) == EXPECTED_EVENT_TYPES, "event schema types do not match")
    _require(
        schemas["export-manifest.schema.json"]["properties"]["completion_status"].get("const") == "complete",
        "export schema cannot accept partial manifests",
    )


def _validate_timestamp(value: Any, label: str) -> None:
    _require(isinstance(value, str) and value.endswith("Z"), f"{label} must be a UTC timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise IntegrationContractError(f"{label} is not a valid timestamp") from error


def _validate_source_reference(reference: Any) -> None:
    _require(isinstance(reference, dict), "source reference must be an object")
    required = {
        "schema_version",
        "source_product",
        "source_version",
        "resource_type",
        "resource_id",
        "resource_schema_version",
        "observed_at",
        "checksum",
    }
    _require(set(reference) == required, "source reference fields do not match")
    _require(reference.get("schema_version") == "nexora-source-reference-v1", "invalid source reference schema")
    _require(reference.get("source_product") == "trd_bot", "invalid source product")
    _require(isinstance(reference.get("source_version"), str) and SEMVER.fullmatch(reference["source_version"]) is not None, "invalid source version")
    _require(all(isinstance(reference.get(key), str) and reference[key] for key in ("resource_type", "resource_id", "resource_schema_version")), "source identity is incomplete")
    _validate_timestamp(reference.get("observed_at"), "source observed_at")
    _require(isinstance(reference.get("checksum"), str) and SOURCE_CHECKSUM.fullmatch(reference["checksum"]) is not None, "invalid source checksum")


def _reject_secret_keys(value: Any, path: str = "fixture") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            _require(key.lower() not in FORBIDDEN_SECRET_KEYS, f"secret-bearing fixture key is forbidden: {path}.{key}")
            _reject_secret_keys(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secret_keys(nested, f"{path}[{index}]")


def validate_fixtures(fixtures: dict[str, dict[str, Any]], contract: dict[str, Any]) -> None:
    expected = {
        "capabilities-response.json",
        "decision-event.json",
        "decision-review-command.json",
        "command-receipt.json",
        "export-manifest.json",
        "incompatible-error.json",
    }
    _require(set(fixtures) == expected, "golden fixture inventory does not match")
    for name, fixture in fixtures.items():
        _reject_secret_keys(fixture, name)

    capabilities = fixtures["capabilities-response.json"]
    _require(capabilities.get("schema_version") == "nexora-integration-capabilities-v1", "invalid capabilities fixture")
    _require(capabilities.get("provider_version") == "0.3.1", "capabilities fixture must prove 0.3.1")
    _require(capabilities.get("contract_versions") == ["nexora-trd-integration-v1"], "capabilities contract mismatch")
    _require(set(capabilities.get("commands", [])) == EXPECTED_COMMAND_TYPES, "capabilities commands mismatch")
    _validate_timestamp(capabilities.get("generated_at"), "capabilities generated_at")

    event = fixtures["decision-event.json"]
    _require(event.get("schema_version") == "trd-integration-event-envelope-v1", "invalid event fixture schema")
    _require(event.get("event_type") in EXPECTED_EVENT_TYPES, "event fixture type is not allowed")
    _require(isinstance(event.get("event_id"), str) and event["event_id"].startswith("evt_"), "invalid event ID")
    _validate_timestamp(event.get("occurred_at"), "event occurred_at")
    _validate_timestamp(event.get("emitted_at"), "event emitted_at")
    _validate_source_reference(event.get("source"))
    aggregate = event.get("aggregate")
    _require(isinstance(aggregate, dict) and set(aggregate) == {"type", "id", "version"}, "invalid event aggregate")
    _require(isinstance(aggregate.get("version"), int) and aggregate["version"] >= 1, "invalid aggregate version")
    _require(isinstance(event.get("idempotency_key"), str) and len(event["idempotency_key"]) >= 16, "invalid event idempotency key")
    _require(isinstance(event.get("payload_checksum"), str) and SOURCE_CHECKSUM.fullmatch(event["payload_checksum"]) is not None, "invalid payload checksum")
    expected_payload_checksum = "sha256:" + hashlib.sha256(
        json.dumps(
            event.get("payload"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    _require(event.get("payload_checksum") == expected_payload_checksum, "payload checksum does not match the canonical payload")

    command = fixtures["decision-review-command.json"]
    _require(command.get("schema_version") == "nexora-decision-review-command-v1", "invalid decision-review fixture")
    _require(command.get("command_type") in EXPECTED_COMMAND_TYPES, "invalid decision-review command type")
    _require(command.get("portfolio_mode") in {"paper", "shadow"}, "decision review must remain Paper/Shadow")
    _validate_timestamp(command.get("reviewed_at"), "decision review reviewed_at")
    _validate_source_reference(command.get("evidence"))

    receipt = fixtures["command-receipt.json"]
    _require(receipt.get("schema_version") == "nexora-command-receipt-v1", "invalid command receipt")
    _require(receipt.get("command_type") in EXPECTED_COMMAND_TYPES, "invalid receipt command type")
    _require(receipt.get("status") in {"accepted", "duplicate"}, "invalid command receipt status")
    _require(isinstance(receipt.get("idempotency_key"), str) and receipt["idempotency_key"], "receipt requires idempotency key")
    _validate_timestamp(receipt.get("accepted_at"), "command accepted_at")

    manifest = fixtures["export-manifest.json"]
    _require(manifest.get("schema_version") == "nexora-export-manifest-v1", "invalid export manifest fixture")
    _require(manifest.get("completion_status") == "complete", "partial export manifests cannot be accepted")
    _require(manifest.get("mode") in set(contract["export"]["modes"]), "invalid fixture export mode")
    _require(manifest.get("profile") in set(contract["export"]["profiles"]), "invalid fixture export profile")
    _require(manifest.get("timezone") == "UTC", "export timezone must be UTC")
    _validate_timestamp(manifest.get("generated_at"), "export generated_at")
    for reference in manifest.get("lineage_references", []):
        _validate_source_reference(reference)
    files = manifest.get("files")
    _require(isinstance(files, list) and files, "export manifest requires at least one file")
    for entry in files:
        _require(isinstance(entry, dict), "manifest file entry must be an object")
        _require(isinstance(entry.get("sha256"), str) and SHA256.fullmatch(entry["sha256"]) is not None, "invalid manifest file checksum")
        _require(isinstance(entry.get("row_count"), int) and entry["row_count"] >= 0, "invalid manifest row count")
        _require(isinstance(entry.get("size_bytes"), int) and entry["size_bytes"] >= 0, "invalid manifest file size")

    error = fixtures["incompatible-error.json"]
    _require(error.get("schema_version") == "nexora-integration-error-v1", "invalid error fixture schema")
    _validate_timestamp(error.get("occurred_at"), "error occurred_at")
    details = error.get("error")
    _require(isinstance(details, dict), "error fixture details must be an object")
    _require(details.get("code") == "INCOMPATIBLE_CONTRACT", "fixture must demonstrate incompatible contract")
    _require(details.get("retryable") is False, "incompatible contract must not be retryable")


def validate_documents() -> None:
    text = DOCUMENT_PATH.read_text(encoding="utf-8")
    markers = (
        "NEX-P0-03",
        "وضعیت: **Candidate**",
        "legacy_read_only_blocked",
        "TRD Bot `0.3.1+`",
        "at_least_once",
        "Idempotency-Key",
        "full snapshot resync",
        "RFC 8785",
        "NEX-P0-04",
        "NEX-P0-03-FREEZE",
        "NEX_P0_03_INTEGRATION_CONTRACT=PASS",
    )
    missing = [marker for marker in markers if marker not in text]
    _require(not missing, f"integration contract document is missing markers: {missing}")
    for path in ADR_PATHS:
        _require(path.is_file(), f"missing ADR: {path.relative_to(ROOT)}")
        adr = path.read_text(encoding="utf-8")
        _require("Accepted candidate for NEX-P0-03" in adr, f"invalid ADR status: {path.name}")
        _require("## Decision" in adr, f"ADR decision is missing: {path.name}")
        _require("## Consequences" in adr, f"ADR consequences are missing: {path.name}")


def main() -> int:
    validate_frozen_baseline()
    contract = load_contract()
    matrix = load_matrix()
    inventory = load_inventory()
    openapi = load_openapi()
    schemas = load_schemas()
    fixtures = load_fixtures()
    validate_contract(contract)
    validate_matrix(matrix)
    validate_inventory(inventory)
    validate_openapi(openapi, contract)
    validate_schemas(schemas)
    validate_fixtures(fixtures, contract)
    validate_documents()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P0_02_PREREQUISITE=PASS")
    print("NEX_P0_03_INTEGRATION_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
