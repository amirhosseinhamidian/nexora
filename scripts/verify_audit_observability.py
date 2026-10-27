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
FREEZE_PATH = ROOT / "artifacts/p1-08/audit-observability-freeze.json"
CONTRACT_CHECKSUM = "5b58a23e8ed75292aab8f923973602e0ae60b168e4d8c580dd1628e76a21d0f0"
P1_07_FREEZE_CHECKSUM = "624d4a8f7e502ba549bc4cf0809aa34e26b988f2082f658c85562162450da009"
P1_07_FREEZE_COMMIT = "6ff8e4f185a51fec0fa2c9a7353d35897fef7eec"
CANDIDATE_SHA = "8aaa4b1fd8a164e325bdc7531aecf72e790df1f3"
CANDIDATE_MESSAGE = "feat(nexora): implement P1-08 audit and observability"
CANDIDATE_PREDECESSOR = "6ff8e4f185a51fec0fa2c9a7353d35897fef7eec"


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


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return _json(path)


def _validate_workflow(
    workflow: object,
    *,
    label: str,
    run_id: int,
    expected_jobs: dict[str, tuple[int, str]],
) -> None:
    _require(isinstance(workflow, dict), f"{label} workflow evidence must be an object")
    _require(workflow.get("run_id") == run_id, f"{label} run ID drift")
    expected_url = f"https://github.com/amirhosseinhamidian/nexora/actions/runs/{run_id}"
    _require(workflow.get("run_url") == expected_url, f"{label} run URL drift")
    _require(workflow.get("head_sha") == CANDIDATE_SHA, f"{label} workflow head SHA drift")
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
        "docs/adr/0022-bounded-private-observability.md": ("Status: Frozen by NEX-P1-08",),
        "docs/v0.1/13-audit-and-observability-foundation.md": (
            "NEX-P1-GAP-004",
            CANDIDATE_SHA,
            "40387123809",
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


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-audit-observability-freeze-v1", "invalid freeze schema")
    _require(record.get("decision_id") == "NEX-P1-08", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "freeze repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "candidate commit message drift")
    _require(record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR, "candidate predecessor drift")

    primary = record.get("github_actions")
    _validate_workflow(
        primary,
        label="audit and observability",
        run_id=40387123809,
        expected_jobs={
            "observability_contract": (121798240329, "observability-contract"),
            "postgresql_17": (121798240976, "postgresql-17"),
            "backend": (121798241108, "backend"),
        },
    )
    _require(primary.get("head_branch") == "feature/v0.1-foundation", "primary workflow branch drift")
    required_markers = {
        "observability_contract": (
            "locked_dependencies_installed",
            "p1_07_freeze_prerequisite_passed",
            "audit_observability_verifier_passed",
            "repository_contract_tests_passed",
        ),
        "postgresql_17": (
            "private_dsn_fixture_created",
            "upgrade_head_passed",
            "append_only_audit_integration_passed",
            "downgrade_base_passed",
            "rebuild_head_passed",
            "migration_drift_check_passed",
        ),
        "backend": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "non_integration_tests_passed",
        ),
    }
    for job_name, markers in required_markers.items():
        for marker in markers:
            _require(primary["jobs"][job_name].get(marker) is True, f"{job_name} did not confirm {marker}")

    regression = record.get("regression_workflows")
    _require(isinstance(regression, dict), "regression workflow evidence must be an object")
    expected_regression = {
        "contracts": (
            40387123861,
            {
                "integration_contract": (121798240069, "integration-contract"),
                "security_boundary": (121798240316, "security-boundary"),
                "technical_baseline": (121798240325, "technical-baseline"),
                "phase_zero_acceptance": (121798240465, "phase-zero-acceptance"),
                "scope_contract": (121798240473, "scope-contract"),
            },
        ),
        "trd_bot_adapter": (
            40387123898,
            {
                "backend": (121798241028, "backend"),
                "adapter_contract": (121798241556, "adapter-contract"),
            },
        ),
        "runtime_foundation": (
            40387123838,
            {
                "backend": (121798240269, "backend"),
                "foundation_contract": (121798240686, "foundation-contract"),
                "web": (121798240986, "web"),
            },
        ),
        "runtime_api_auth": (
            40387124010,
            {
                "cross_language_contract": (121798240678, "cross-language-contract"),
                "runtime_contract": (121798241100, "runtime-contract"),
                "postgresql_17": (121798241117, "postgresql-17"),
                "backend": (121798241400, "backend"),
            },
        ),
        "application_composition": (
            40387123763,
            {
                "composition_contract": (121798242051, "composition-contract"),
                "backend": (121798242453, "backend"),
            },
        ),
        "phase_one_readiness": (
            40387123810,
            {
                "web": (121798240655, "web"),
                "backend": (121798240953, "backend"),
                "readiness_contract": (121798241085, "readiness-contract"),
            },
        ),
        "single_owner_identity_runtime": (
            40387123779,
            {
                "backend": (121798240587, "backend"),
                "postgresql_17": (121798240612, "postgresql-17"),
                "private_topology": (121798240698, "private-topology"),
                "identity_contract": (121798240775, "identity-contract"),
            },
        ),
        "postgresql_schema": (
            40387123862,
            {
                "database_contract": (121798240673, "database-contract"),
                "postgresql_17": (121798241179, "postgresql-17"),
                "backend": (121798241350, "backend"),
            },
        ),
        "durable_jobs_outbox": (
            40387123868,
            {
                "durable_contract": (121798240214, "durable-contract"),
                "backend": (121798240524, "backend"),
                "postgresql_17": (121798240549, "postgresql-17"),
            },
        ),
    }
    _require(set(regression) == set(expected_regression), "regression workflow inventory mismatch")
    for label, (run_id, jobs) in expected_regression.items():
        _validate_workflow(regression[label], label=label, run_id=run_id, expected_jobs=jobs)

    evidence = record.get("audit_observability_contract")
    _require(isinstance(evidence, dict), "audit observability contract evidence must be an object")
    _require(evidence.get("schema_version") == contract.get("schema_version"), "contract schema mismatch")
    _require(evidence.get("checksum") == CONTRACT_CHECKSUM, "recorded contract checksum drift")
    _require(evidence.get("checksum") == canonical_checksum(contract), "contract checksum mismatch")

    prerequisite = record.get("p1_07_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-07 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-07", "P1-07 prerequisite decision drift")
    _require(prerequisite.get("frozen") is True, "P1-07 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P1_07_FREEZE_COMMIT, "P1-07 freeze commit drift")
    _require(
        prerequisite.get("freeze_record_checksum")
        == canonical_checksum(_json(P1_07_FREEZE_PATH))
        == P1_07_FREEZE_CHECKSUM,
        "P1-07 freeze checksum mismatch",
    )

    _require(record.get("recorded_on") == "2026-10-26", "invalid freeze record date")
    _require(record.get("frozen") is True, "P1-08 is not frozen")
    _require(record.get("closed_gaps") == ["NEX-P1-GAP-004"], "frozen gap inventory drift")
    for key in (
        "production_readiness_claimed",
        "public_metrics_endpoint",
        "external_telemetry_export",
        "public_internet_profile",
        "live_execution_capability",
        "exchange_credentials",
        "wallet_capability",
        "autonomous_ai_execution",
    ):
        _require(record.get(key) is False, f"freeze record cannot enable {key}")
    _require(record.get("next_allowed_stage") == "NEX-P1-09", "post-freeze stage drift")


def main() -> int:
    validate_frozen_p1_07()
    contract = load_contract()
    validate_contract(contract)
    validate_files_and_runtime_markers()
    freeze_record = load_freeze_record()
    validate_freeze_record(freeze_record, contract)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print(f"candidate_commit_sha={freeze_record['candidate_commit_sha']}")
    print("NEX_P1_07_PREREQUISITE=PASS")
    print("NEX_P1_08_AUDIT_OBSERVABILITY=PASS")
    print("NEX_P1_08_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
