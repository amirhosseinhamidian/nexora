#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-audit-observability.json"
P1_07_FREEZE_PATH = ROOT / "artifacts/p1-07/runtime-api-auth-freeze.json"
CONTRACT_CHECKSUM = "5b58a23e8ed75292aab8f923973602e0ae60b168e4d8c580dd1628e76a21d0f0"
P1_07_FREEZE_CHECKSUM = "624d4a8f7e502ba549bc4cf0809aa34e26b988f2082f658c85562162450da009"
P1_07_FREEZE_COMMIT = "6ff8e4f185a51fec0fa2c9a7353d35897fef7eec"


class AuditObservabilityContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditObservabilityContractError(message)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), f"{path.name} must contain an object")
    return payload


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _json(path)


def validate_frozen_p1_07() -> None:
    path = ROOT / "scripts/verify_runtime_api_auth.py"
    spec = importlib.util.spec_from_file_location("verify_runtime_api_auth", path)
    if spec is None or spec.loader is None:
        raise AuditObservabilityContractError("unable to load frozen P1-07 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_phase_one_readiness()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_generated_contracts()
    module.validate_openapi()
    module.validate_files_and_documents()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-audit-observability-v1", "invalid contract schema")
    _require(contract.get("decision_id") == "NEX-P1-08", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-26", "invalid decision date")
    _require(contract.get("status") == "candidate", "P1-08 must remain candidate")

    prerequisite = contract.get("p1_07_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-07 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-07", "P1-07 prerequisite decision drift")
    _require(prerequisite.get("frozen") is True, "P1-07 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P1_07_FREEZE_COMMIT, "P1-07 freeze commit drift")
    _require(prerequisite.get("freeze_record_checksum") == P1_07_FREEZE_CHECKSUM, "P1-07 checksum drift")
    _require(canonical_checksum(_json(P1_07_FREEZE_PATH)) == P1_07_FREEZE_CHECKSUM, "P1-07 record drift")
    _require(contract.get("closes_gaps") == ["NEX-P1-GAP-004"], "P1-08 gap ownership drift")

    logging = contract.get("structured_logging")
    _require(isinstance(logging, dict), "structured logging contract must be an object")
    expected_logging = {
        "schema_version": "nexora-observability-event-v1",
        "encoding": "json_lines_utf8",
        "canonical_time": "UTC",
        "correlation_id_propagated": True,
        "request_duration_ms_recorded": True,
        "raw_query_string_logged": False,
        "request_or_response_body_logged": False,
        "exception_message_logged": False,
        "secret_redaction_recursive": True,
        "production_log_file_required": True,
        "rotation_strategy": "size_bounded_local_file",
        "rotation_max_bytes": 10_485_760,
        "rotation_backup_count": 30,
        "retention_days": 30,
    }
    _require(logging == expected_logging, "structured logging policy drift")

    metrics = contract.get("runtime_metrics")
    _require(isinstance(metrics, dict), "runtime metrics contract must be an object")
    _require(metrics.get("schema_version") == "nexora-runtime-metrics-v1", "metric schema drift")
    _require(metrics.get("storage") == "bounded_in_process_snapshot", "metric storage drift")
    _require(metrics.get("external_collector_required") is False, "external collector cannot become required")
    _require(
        metrics.get("request_dimensions") == ["method", "route_template", "status_class"],
        "request metric dimensions drift",
    )
    _require(metrics.get("request_duration_buckets_ms") == [25, 50, 100, 300, 1000, 5000], "buckets drift")
    _require(metrics.get("maximum_route_dimensions") == 64, "route metric cardinality limit drift")
    _require(metrics.get("raw_path_or_query_labels_forbidden") is True, "raw paths cannot become labels")
    _require(metrics.get("owner_or_session_labels_forbidden") is True, "identity cannot become a metric label")
    _require(metrics.get("retention_days_when_exported") == 90, "metric retention drift")

    readiness = contract.get("readiness")
    _require(isinstance(readiness, dict), "readiness contract must be an object")
    _require(readiness.get("endpoint") == "/health/ready", "readiness endpoint drift")
    _require(readiness.get("public_openapi_operation") is False, "readiness cannot become a public operation")
    _require(readiness.get("dependencies") == ["database", "identity", "trd_bot"], "dependency inventory drift")
    _require(readiness.get("fails_closed") is True, "readiness must fail closed")
    _require(readiness.get("does_not_expose_targets_or_credentials") is True, "readiness may expose secrets")

    audit = contract.get("security_audit")
    _require(isinstance(audit, dict), "security audit contract must be an object")
    _require(audit.get("persistence") == "postgresql_append_only", "audit persistence drift")
    _require(audit.get("mutation_trigger_enforced") is True, "audit immutability cannot be weakened")
    _require(audit.get("metadata_scalar_only") is True, "audit metadata must remain bounded")
    _require(audit.get("metadata_max_bytes") == 4096, "audit metadata size drift")
    _require(audit.get("secret_bearing_metadata_rejected") is True, "audit secret guard is required")
    _require(audit.get("retention_days") == 400, "audit retention drift")

    worker = contract.get("worker_observability")
    _require(isinstance(worker, dict), "worker observability contract must be an object")
    for key in ("observer_injected", "cycle_aggregate_only", "failure_reason_code_bounded"):
        _require(worker.get(key) is True, f"worker observability requires {key}")
    _require(worker.get("handler_exception_message_logged") is False, "handler error messages cannot be logged")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and security, "security boundary must be an object")
    for capability, enabled in security.items():
        _require(enabled is False, f"forbidden observability capability enabled: {capability}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_freeze") is True, "P1-08 is not ready for freeze")
    _require(transition.get("next_allowed_stage") == "NEX-P1-08-FREEZE", "next stage must be P1-08 freeze")
    _require(transition.get("post_freeze_stage") == "NEX-P1-09", "post-freeze stage drift")
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "audit observability contract drift")


def validate_files_and_runtime_markers() -> None:
    required = {
        "apps/server/src/nexora/observability.py": (
            "nexora-observability-event-v1",
            "RotatingFileHandler",
            "class RuntimeMetrics",
            "def redact_sensitive",
        ),
        "apps/server/src/nexora/security_audit.py": (
            "AUDIT_METADATA_MAX_BYTES",
            "sanitize_audit_metadata",
            "secret-bearing audit metadata key is forbidden",
        ),
        "apps/server/src/nexora/api.py": (
            "observability_boundary",
            "ReadinessSnapshot",
            "database_pool_values",
        ),
        "apps/server/src/nexora/durable_worker.py": ("class WorkerObserver", "observe_job_cycle"),
        "apps/server/src/nexora/adapters/postgresql/models.py": (
            "event_type_nonempty",
            "class SecurityAuditEvent",
        ),
        "alembic/versions/20261026_0003_single_owner_identity_runtime.py": (
            "security_audit_events_immutable",
            "reject_security_audit_mutation",
        ),
        "apps/server/tests/test_observability.py": ("test_structured_formatter_redacts_nested_secrets",),
        "docs/adr/0022-bounded-private-observability.md": ("Status: Accepted by NEX-P1-08 candidate",),
        "docs/v0.1/13-audit-and-observability-foundation.md": (
            "NEX-P1-GAP-004",
            "NEX-P1-09",
        ),
        ".github/workflows/audit-observability.yml": ("Audit and observability",),
    }
    for relative, markers in required.items():
        path = ROOT / relative
        _require(path.is_file(), f"missing P1-08 file: {relative}")
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in content, f"missing P1-08 marker in {relative}: {marker}")


def main() -> int:
    validate_frozen_p1_07()
    contract = load_contract()
    validate_contract(contract)
    validate_files_and_runtime_markers()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_07_PREREQUISITE=PASS")
    print("NEX_P1_08_AUDIT_OBSERVABILITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
