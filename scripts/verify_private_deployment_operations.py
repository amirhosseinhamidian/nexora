#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-private-deployment-operations.json"
P1_11_FREEZE_PATH = ROOT / "artifacts/p1-11/authenticated-web-shell-freeze.json"
FREEZE_PATH = ROOT / "artifacts/p1-12/private-deployment-operations-freeze.json"
CONTRACT_CHECKSUM = "dbafedfd72018c6fed40e74e4fbd579d6d2abe8022dbb397d146793cb71524af"
P1_11_FREEZE_CHECKSUM = "fc955113cdd72f5d5099a1f5988989ee36589b2a30801461ee908bd0b539a1cc"
P1_11_FREEZE_COMMIT = "6214b79786b0f92d8f06c4c43b3533db717b5ce2"
CANDIDATE_SHA = "86651f1b49343e7e609ee5f671ad00eb83822ca9"
CANDIDATE_TREE_SHA = "8b65ce3e47ca6eeb95552c8b4621b20990c48ecf"
CANDIDATE_MESSAGE = "fix(nexora): repair P1-12 regression CI gates"
CANDIDATE_PREDECESSOR = "18d5956b335897e7681c39a012a8cf717c1e09aa"


class PrivateDeploymentOperationsContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PrivateDeploymentOperationsContractError(message)


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


def validate_frozen_p1_11() -> None:
    path = ROOT / "scripts/verify_authenticated_web_shell.py"
    spec = importlib.util.spec_from_file_location("verify_authenticated_web_shell", path)
    if spec is None or spec.loader is None:
        raise PrivateDeploymentOperationsContractError("unable to load frozen P1-11 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_p1_10()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_files_and_runtime_markers()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-private-deployment-operations-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P1-12", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-27", "invalid decision date")
    _require(contract.get("status") == "candidate", "P1-12 must remain candidate")

    prerequisite = contract.get("p1_11_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-11 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-11", "P1-11 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P1-11 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P1_11_FREEZE_COMMIT, "P1-11 commit drift")
    _require(
        prerequisite.get("freeze_record_path") == "artifacts/p1-11/authenticated-web-shell-freeze.json",
        "P1-11 freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P1_11_FREEZE_CHECKSUM, "P1-11 checksum drift")
    _require(canonical_checksum(_json(P1_11_FREEZE_PATH)) == P1_11_FREEZE_CHECKSUM, "P1-11 record drift")
    _require(contract.get("closes_gaps") == ["NEX-P1-GAP-008"], "P1-12 gap ownership drift")

    topology = contract.get("topology")
    _require(isinstance(topology, dict), "topology must be an object")
    _require(topology.get("profile") == "private_single_host", "deployment profile drift")
    _require(topology.get("services") == ["ingress", "web", "api", "worker", "postgresql"], "service drift")
    _require(topology.get("only_host_port") == 443, "only HTTPS 443 may be exposed")
    _require(topology.get("bind_scope") == "authenticated_private_overlay_address", "bind scope drift")
    _require(topology.get("tls_minimum") == "1.3", "TLS minimum drift")
    for key in ("postgresql_host_port", "worker_host_port"):
        _require(topology.get(key) is False, f"topology forbids {key}")
    for key in ("bounded_container_logs", "health_ordered_startup", "graceful_shutdown"):
        _require(topology.get(key) is True, f"topology requires {key}")

    secrets = contract.get("secrets")
    _require(isinstance(secrets, dict), "secrets must be an object")
    _require(secrets.get("injection") == "absolute_read_only_mounted_files", "secret injection drift")
    for key in ("committed_values", "included_in_backup", "included_in_log"):
        _require(secrets.get(key) is False, f"secret boundary forbids {key}")
    _require(secrets.get("age_private_identity_on_runtime_host_at_rest") is False, "offline identity drift")

    backup = contract.get("backup")
    _require(isinstance(backup, dict), "backup must be an object")
    _require(backup.get("database_format") == "postgresql_custom", "database backup format drift")
    _require(backup.get("encryption") == "age_x25519_offline_recipient", "backup encryption drift")
    _require(backup.get("manifest_checksum") == "sha256", "backup checksum drift")
    for key in ("artifacts_included", "atomic_publish"):
        _require(backup.get(key) is True, f"backup requires {key}")
    _require(backup.get("runtime_copy_counts_as_offsite") is False, "runtime copy cannot count as offsite")
    _require(backup.get("minimum_offsite_copies") == 1, "one offsite copy is required")
    _require(backup.get("recovery_point_objective_hours") == 24, "RPO drift")
    _require(backup.get("retention_tiers") == {"daily": 14, "weekly": 8, "monthly": 12}, "backup tiers drift")

    restore = contract.get("restore")
    _require(isinstance(restore, dict), "restore must be an object")
    for key in (
        "owner_present",
        "recent_reauthentication",
        "runtime_stopped",
        "encrypted_copy_verified_before_decrypt",
        "content_checksums_verified",
        "sessions_revoked",
        "service_tokens_revoked",
        "service_token_rotation_required",
    ):
        _require(restore.get(key) is True, f"restore requires {key}")
    _require(restore.get("recovery_time_objective_hours") == 4, "RTO drift")

    retention = contract.get("retention")
    _require(isinstance(retention, dict), "retention must be an object")
    for key in ("idempotent", "dry_run_default", "owner_approval_for_apply", "manifest_before_delete"):
        _require(retention.get(key) is True, f"retention requires {key}")
    _require(retention.get("audit_before_delete") is True, "retention audit is required")
    _require(
        retention.get("automatic_deletion_scope")
        == ["expired_unpinned_export_artifacts", "backups_outside_retention_tiers"],
        "retention deletion scope drift",
    )
    _require(retention.get("immutable_evidence_excluded") is True, "immutable evidence must be protected")
    _require(retention.get("pinned_artifacts_excluded") is True, "pinned artifacts must be protected")

    capacity = contract.get("capacity_and_overload")
    _require(isinstance(capacity, dict), "capacity and overload must be an object")
    _require(capacity.get("database_soft_limit_gib") == 20, "database soft limit drift")
    _require(capacity.get("artifact_soft_limit_gib") == 100, "artifact soft limit drift")
    _require(capacity.get("minimum_free_storage_percent") == 20, "free-space reserve drift")
    _require(capacity.get("interactive_requests_per_second") == {"sustained": 10, "burst": 25}, "rate drift")
    _require(capacity.get("overload_status") == 429, "overload status drift")
    for key in ("retry_after_required", "bounded_worker_concurrency", "durable_work_queued"):
        _require(capacity.get(key) is True, f"overload policy requires {key}")
    _require(capacity.get("immutable_evidence_dropped") is False, "overload cannot drop evidence")

    acceptance = contract.get("acceptance_boundary")
    _require(isinstance(acceptance, dict), "acceptance boundary must be an object")
    _require(acceptance.get("implementation_and_smoke_tooling_delivered") is True, "tooling not delivered")
    _require(acceptance.get("actual_capacity_benchmark_deferred_to") == "NEX-P1-13", "benchmark owner drift")
    _require(acceptance.get("actual_backup_restore_drill_deferred_to") == "NEX-P1-13", "drill owner drift")
    _require(acceptance.get("production_readiness_claimed") is False, "production readiness is deferred")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and security, "security boundary must be an object")
    for capability, enabled in security.items():
        _require(enabled is False, f"forbidden capability enabled: {capability}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_freeze") is True, "P1-12 is not ready for freeze")
    _require(transition.get("next_allowed_stage") == "NEX-P1-12-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P1-13", "post-freeze stage drift")
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "private operations contract drift")


def validate_files_and_runtime_markers() -> None:
    required = {
        "infra/compose/private-single-host.yml": (
            "${NEXORA_PRIVATE_BIND_ADDRESS:?private overlay address required}:443:443",
            'profiles: ["operations"]',
            '"--run"',
            'max-size: "10m"',
        ),
        "infra/operations/Dockerfile": ("FROM postgres:17.6-bookworm", "age=1.1.1-1+b3"),
        "infra/operations/create-backup.sh": ("pg_dump", "age", "publish-backup"),
        "infra/operations/restore-backup.sh": (
            "NEXORA_RESTORE_RECENT_REAUTHENTICATION",
            "verify-backup",
            "UPDATE nexora.sessions",
        ),
        "infra/operations/run-retention.sh": ("NEXORA_RETENTION_OWNER_APPROVED",),
        "apps/server/src/nexora/overload.py": ("class InteractiveRequestGate", "retry_after_seconds"),
        "apps/server/src/nexora/private_operations.py": (
            "age_x25519_offline_recipient",
            "delete_expired_unpinned_export",
            '"immutable_evidence_dropped": False',
        ),
        "scripts/benchmark_private_runtime.py": ("Retry-After", "SOURCE_COMMIT_SHA"),
        "docs/adr/0026-private-single-host-operations.md": ("Status: Frozen by NEX-P1-12",),
        "docs/v0.1/17-private-deployment-and-operations.md": ("NEX-P1-GAP-008", "NEX-P1-13"),
        ".github/workflows/private-deployment-operations.yml": ("Private deployment and operations",),
    }
    for relative, markers in required.items():
        path = ROOT / relative
        _require(path.is_file(), f"missing P1-12 file: {relative}")
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in content, f"missing P1-12 marker in {relative}: {marker}")

    compose = (ROOT / "infra/compose/private-single-host.yml").read_text(encoding="utf-8")
    _require("5432:5432" not in compose, "PostgreSQL cannot expose a host port")
    _require("8000:8000" not in compose and "3000:3000" not in compose, "internal services cannot expose ports")
    _require("public_internet" not in compose, "public deployment is forbidden")
    inventory = (ROOT / "infra/operations/secret-inventory.example.json").read_text(encoding="utf-8")
    for forbidden in ("AGE-SECRET-KEY-", "postgresql+psycopg://", "Bearer "):
        _require(forbidden not in inventory, f"secret inventory contains forbidden material: {forbidden}")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(
        record.get("schema_version") == "nexora-private-deployment-operations-freeze-v1",
        "invalid freeze schema",
    )
    _require(record.get("decision_id") == "NEX-P1-12", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_tree_sha") == CANDIDATE_TREE_SHA, "candidate tree drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "commit message drift")
    _require(record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR, "candidate parent drift")

    primary = record.get("github_actions")
    _validate_workflow(
        primary,
        label="private deployment and operations",
        run_id=40645349248,
        expected_jobs={
            "backend": (122672764034, "backend"),
            "private_topology": (122672764174, "private-topology"),
            "operations_contract": (122672764233, "operations-contract"),
        },
    )
    _require(primary.get("head_branch") == "feature/v0.1-foundation", "primary workflow branch drift")
    required_markers = {
        "backend": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "backend_and_repository_tests_passed",
        ),
        "private_topology": (
            "compose_topology_validated",
            "operations_image_built",
        ),
        "operations_contract": (
            "p1_11_freeze_prerequisite_passed",
            "private_operations_verifier_passed",
            "repository_contract_tests_passed",
            "operations_shell_syntax_passed",
        ),
    }
    for job_name, markers in required_markers.items():
        for marker in markers:
            _require(primary["jobs"][job_name].get(marker) is True, f"{job_name} did not confirm {marker}")

    regression = record.get("regression_workflows")
    _require(isinstance(regression, dict), "regression workflow evidence must be an object")
    expected_regression = {
        "application_composition": (
            40645349250,
            {
                "backend": (122672763673, "backend"),
                "composition_contract": (122672763970, "composition-contract"),
            },
        ),
        "artifact_export_storage": (
            40645349290,
            {
                "backend": (122672764071, "backend"),
                "storage_contract": (122672764254, "storage-contract"),
                "storage_runtime": (122672764304, "storage-runtime"),
            },
        ),
        "audit_observability": (
            40645349284,
            {
                "backend": (122672763915, "backend"),
                "observability_contract": (122672764201, "observability-contract"),
                "postgresql_17": (122672764277, "postgresql-17"),
            },
        ),
        "authenticated_web_shell": (
            40645349259,
            {
                "backend": (122672763965, "backend"),
                "browser": (122672764287, "browser"),
                "web": (122672764306, "web"),
                "web_shell_contract": (122672764380, "web-shell-contract"),
            },
        ),
        "contracts": (
            40645349318,
            {
                "integration_contract": (122672764096, "integration-contract"),
                "security_boundary": (122672764282, "security-boundary"),
                "phase_zero_acceptance": (122672764292, "phase-zero-acceptance"),
                "technical_baseline": (122672764300, "technical-baseline"),
                "scope_contract": (122672764350, "scope-contract"),
            },
        ),
        "durable_jobs_outbox": (
            40645349272,
            {
                "postgresql_17": (122672763852, "postgresql-17"),
                "durable_contract": (122672764202, "durable-contract"),
                "backend": (122672764232, "backend"),
            },
        ),
        "phase_one_readiness": (
            40645349367,
            {
                "readiness_contract": (122672763981, "readiness-contract"),
                "web": (122672764331, "web"),
                "backend": (122672764366, "backend"),
            },
        ),
        "postgresql_schema": (
            40645349329,
            {
                "database_contract": (122672763713, "database-contract"),
                "backend": (122672764074, "backend"),
                "postgresql_17": (122672764258, "postgresql-17"),
            },
        ),
        "runtime_api_auth": (
            40645349273,
            {
                "runtime_contract": (122672763859, "runtime-contract"),
                "cross_language_contract": (122672764087, "cross-language-contract"),
                "postgresql_17": (122672764108, "postgresql-17"),
                "backend": (122672764143, "backend"),
            },
        ),
        "runtime_foundation": (
            40645349274,
            {
                "backend": (122672763817, "backend"),
                "web": (122672764075, "web"),
                "foundation_contract": (122672764129, "foundation-contract"),
            },
        ),
        "single_owner_identity_runtime": (
            40645349245,
            {
                "identity_contract": (122672763920, "identity-contract"),
                "postgresql_17": (122672764288, "postgresql-17"),
                "private_topology": (122672764336, "private-topology"),
                "backend": (122672764346, "backend"),
            },
        ),
        "trd_bot_adapter": (
            40645349344,
            {
                "adapter_contract": (122672764069, "adapter-contract"),
                "backend": (122672764339, "backend"),
            },
        ),
        "trd_bot_sync_runtime": (
            40645349254,
            {
                "backend": (122672764058, "backend"),
                "postgresql_17": (122672764147, "postgresql-17"),
                "sync_contract": (122672764301, "sync-contract"),
            },
        ),
    }
    _require(set(regression) == set(expected_regression), "regression workflow inventory mismatch")
    for label, (run_id, jobs) in expected_regression.items():
        _validate_workflow(regression[label], label=label, run_id=run_id, expected_jobs=jobs)

    evidence = record.get("private_deployment_operations_contract")
    _require(isinstance(evidence, dict), "private operations evidence must be an object")
    _require(evidence.get("schema_version") == contract.get("schema_version"), "contract schema mismatch")
    _require(
        evidence.get("path") == "contracts/nexora-v0.1-private-deployment-operations.json",
        "contract path drift",
    )
    _require(evidence.get("checksum") == CONTRACT_CHECKSUM, "recorded contract checksum drift")
    _require(evidence.get("checksum") == canonical_checksum(contract), "contract checksum mismatch")

    prerequisite = record.get("p1_11_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-11 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-11", "P1-11 prerequisite decision drift")
    _require(prerequisite.get("frozen") is True, "P1-11 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P1_11_FREEZE_COMMIT, "P1-11 freeze commit drift")
    _require(
        prerequisite.get("freeze_record_path") == "artifacts/p1-11/authenticated-web-shell-freeze.json",
        "P1-11 path drift",
    )
    _require(
        prerequisite.get("freeze_record_checksum")
        == canonical_checksum(_json(P1_11_FREEZE_PATH))
        == P1_11_FREEZE_CHECKSUM,
        "P1-11 freeze checksum mismatch",
    )

    _require(record.get("recorded_on") == "2026-10-28", "invalid freeze record date")
    _require(record.get("frozen") is True, "P1-12 is not frozen")
    _require(record.get("closed_gaps") == ["NEX-P1-GAP-008"], "frozen gap inventory drift")
    _require(record.get("production_readiness_claimed") is False, "production readiness is deferred")
    _require(record.get("actual_capacity_benchmark_completed") is False, "capacity benchmark is deferred")
    _require(record.get("actual_backup_restore_drill_completed") is False, "restore drill is deferred")
    for key in (
        "public_internet_profile",
        "live_order_capability",
        "exchange_credentials",
        "wallet_capability",
        "autonomous_ai_execution",
        "multi_user",
    ):
        _require(record.get(key) is False, f"freeze record cannot enable {key}")
    _require(record.get("next_allowed_stage") == "NEX-P1-13", "post-freeze stage drift")


def main() -> int:
    validate_frozen_p1_11()
    contract = load_contract()
    validate_contract(contract)
    validate_files_and_runtime_markers()
    validate_freeze_record(load_freeze_record(), contract)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_11_PREREQUISITE=PASS")
    print("NEX_P1_12_PRIVATE_DEPLOYMENT_OPERATIONS=PASS")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print("NEX_P1_12_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
