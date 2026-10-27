#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/nexora-v0.1-artifact-export-storage.json"
P1_09_FREEZE_PATH = ROOT / "artifacts/p1-09/trd-bot-sync-runtime-freeze.json"
FREEZE_PATH = ROOT / "artifacts/p1-10/artifact-export-storage-freeze.json"
CONTRACT_CHECKSUM = "a0badfe42b047b4e69089fbc02425d8a1c51d70465148418948835d95ccdd694"
P1_09_FREEZE_CHECKSUM = "5b29d6bc22652acc2576f9027a8eb362c41303f8ecfffaf692ba1bcccdcaec9d"
P1_09_FREEZE_COMMIT = "e3d724074b8ac276f68ebf5d3e100c86a711f672"
CANDIDATE_SHA = "707795735e156ebbd973f08709e52c5a994e2d17"
CANDIDATE_MESSAGE = "feat(nexora): implement P1-10 artifact and export storage"
CANDIDATE_PREDECESSOR = "e3d724074b8ac276f68ebf5d3e100c86a711f672"


class ArtifactExportStorageContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactExportStorageContractError(message)


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


def validate_frozen_p1_09() -> None:
    path = ROOT / "scripts/verify_trd_bot_sync_runtime.py"
    spec = importlib.util.spec_from_file_location("verify_trd_bot_sync_runtime", path)
    if spec is None or spec.loader is None:
        raise ArtifactExportStorageContractError("unable to load frozen P1-09 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_frozen_p1_08()
    contract = module.load_contract()
    module.validate_contract(contract)
    module.validate_files_and_runtime_markers()
    module.validate_freeze_record(module.load_freeze_record(), contract)


def validate_contract(contract: dict[str, Any]) -> None:
    _require(contract.get("schema_version") == "nexora-artifact-export-storage-v1", "invalid schema")
    _require(contract.get("decision_id") == "NEX-P1-10", "invalid decision ID")
    _require(contract.get("decision_date") == "2026-10-27", "invalid decision date")
    _require(contract.get("status") == "candidate", "P1-10 must remain candidate")

    prerequisite = contract.get("p1_09_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-09 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-09", "P1-09 prerequisite drift")
    _require(prerequisite.get("frozen") is True, "P1-09 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P1_09_FREEZE_COMMIT, "P1-09 commit drift")
    _require(
        prerequisite.get("freeze_record_path") == "artifacts/p1-09/trd-bot-sync-runtime-freeze.json",
        "P1-09 freeze path drift",
    )
    _require(prerequisite.get("freeze_record_checksum") == P1_09_FREEZE_CHECKSUM, "P1-09 checksum drift")
    _require(canonical_checksum(_json(P1_09_FREEZE_PATH)) == P1_09_FREEZE_CHECKSUM, "P1-09 record drift")
    _require(contract.get("closes_gaps") == ["NEX-P1-GAP-006"], "P1-10 gap ownership drift")

    adapter = contract.get("adapter")
    _require(isinstance(adapter, dict), "adapter must be an object")
    _require(adapter.get("name") == "versioned_local_filesystem_adapter", "adapter name drift")
    _require(adapter.get("root_environment_variable") == "NEXORA_ARTIFACT_ROOT", "artifact root drift")
    _require(
        adapter.get("path_strategy") == "owner_namespace_type_artifact_id_version",
        "artifact path strategy drift",
    )
    _require(adapter.get("namespaces") == ["source", "export", "backup"], "namespace inventory drift")
    for key in ("root_must_be_absolute", "root_must_not_be_symbolic_link", "owner_scoped"):
        _require(adapter.get(key) is True, f"adapter requires {key}")
    _require(adapter.get("published_content_mode") == "0440", "content mode drift")
    _require(adapter.get("published_directory_mode") == "0550", "directory mode drift")
    _require(adapter.get("public_network_access") is False, "artifact root cannot be public")
    _require(adapter.get("s3_compatible_adapter_implemented") is False, "S3 adapter is deferred")

    publication = contract.get("publication")
    _require(isinstance(publication, dict), "publication must be an object")
    _require(
        publication.get("atomic_strategy") == "same_parent_stage_write_fsync_directory_rename_fsync_parent",
        "atomic strategy drift",
    )
    _require(publication.get("manifest_schema") == "nexora-artifact-manifest-v1", "manifest schema drift")
    _require(publication.get("content_checksum") == "sha256", "content checksum drift")
    for key in (
        "manifest_canonical_json",
        "content_size_recorded",
        "media_type_recorded",
        "content_schema_version_recorded",
        "immutable_after_publish",
        "identical_retry_idempotent",
        "conflicting_retry_rejected",
        "read_verifies_identity_size_and_checksum",
    ):
        _require(publication.get(key) is True, f"publication requires {key}")
    _require(publication.get("partial_publish_visible") is False, "partial publication cannot be visible")

    export = contract.get("export_bundle")
    _require(isinstance(export, dict), "export bundle must be an object")
    _require(export.get("source_manifest_schema") == "nexora-export-manifest-v1", "export schema drift")
    _require(export.get("bundle_schema") == "nexora-export-bundle-v1", "bundle schema drift")
    _require(export.get("bundle_media_type") == "application/zip", "bundle media type drift")
    _require(
        export.get("supported_embedded_formats") == ["json", "jsonl", "csv", "parquet", "zip_bundle"],
        "embedded format inventory drift",
    )
    _require(export.get("profiles") == ["private", "ai_safe"], "export profile inventory drift")
    for key in (
        "deterministic_entry_order",
        "deterministic_entry_metadata",
        "exact_file_inventory_required",
        "per_file_size_verified",
        "per_file_checksum_verified",
    ):
        _require(export.get(key) is True, f"export bundle requires {key}")
    _require(export.get("partial_export_accepted") is False, "partial export cannot be accepted")
    _require(export.get("unsafe_relative_paths_accepted") is False, "unsafe export paths cannot be accepted")

    capacity = contract.get("capacity")
    _require(isinstance(capacity, dict), "capacity must be an object")
    _require(capacity.get("soft_quota_gib") == 100, "soft quota drift")
    _require(capacity.get("hard_quota_gib") == 160, "hard quota drift")
    _require(capacity.get("minimum_free_storage_percent") == 20, "free-space reserve drift")
    _require(capacity.get("alert_thresholds_percent") == [70, 85, 95], "capacity thresholds drift")
    _require(
        capacity.get("final_threshold_action") == "write_protect_noncritical_artifacts",
        "final threshold action drift",
    )
    _require(capacity.get("hard_quota_fails_closed_for_all_writes") is True, "hard quota must fail closed")
    _require(
        capacity.get("free_space_reserve_fails_closed_for_all_writes") is True,
        "free-space reserve must fail closed",
    )
    _require(
        capacity.get("critical_retention_classes") == ["immutable_source_evidence", "financial_record", "backup"],
        "critical retention classes drift",
    )

    retention = contract.get("retention")
    _require(isinstance(retention, dict), "retention must be an object")
    _require(retention.get("dry_run_only_in_p1_10") is True, "P1-10 retention must remain dry-run only")
    _require(retention.get("unpinned_export_days") == 30, "unpinned export retention drift")
    for key in (
        "immutable_source_evidence_auto_delete",
        "financial_record_auto_delete",
        "pinned_export_auto_delete",
    ):
        _require(retention.get(key) is False, f"retention cannot enable {key}")
    _require(retention.get("backup_deletion_owned_by") == "NEX-P1-12", "backup retention owner drift")
    _require(retention.get("dry_run_idempotent") is True, "retention dry-run must be idempotent")

    reconciliation = contract.get("reconciliation")
    _require(isinstance(reconciliation, dict), "reconciliation must be an object")
    for key in (
        "manifest_inventory",
        "content_integrity_verification",
        "orphan_content_detection",
        "abandoned_staging_detection",
    ):
        _require(reconciliation.get(key) is True, f"reconciliation requires {key}")
    _require(
        reconciliation.get("automatic_evidence_deletion") is False,
        "reconciliation cannot delete evidence automatically",
    )

    runtime = contract.get("runtime")
    _require(isinstance(runtime, dict), "runtime must be an object")
    _require(runtime.get("private_compose_volume") == "nexora-artifacts", "artifact volume drift")
    _require(runtime.get("dedicated_runtime_mount") == "/var/lib/nexora/artifacts", "artifact mount drift")
    _require(runtime.get("api_container_registration") is True, "private API storage registration is required")
    _require(runtime.get("public_static_mount") is False, "artifact storage cannot be a public static mount")
    _require(runtime.get("unauthenticated_download_route") is False, "unauthenticated download is forbidden")
    _require(runtime.get("authenticated_download_route_owned_by") == "NEX-P1-11", "download owner drift")
    _require(runtime.get("local_compose_port_is_infrastructure_only") is True, "compose port boundary drift")

    security = contract.get("security_boundary")
    _require(isinstance(security, dict) and security, "security boundary must be an object")
    for capability, enabled in security.items():
        _require(enabled is False, f"forbidden artifact capability enabled: {capability}")

    transition = contract.get("transition")
    _require(isinstance(transition, dict), "transition must be an object")
    _require(transition.get("ready_for_freeze") is True, "P1-10 is not ready for freeze")
    _require(transition.get("next_allowed_stage") == "NEX-P1-10-FREEZE", "next stage drift")
    _require(transition.get("post_freeze_stage") == "NEX-P1-11", "post-freeze stage drift")
    _require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "artifact storage contract drift")


def validate_files_and_runtime_markers() -> None:
    required = {
        "apps/server/src/nexora/artifact_storage.py": (
            "class ArtifactStorage(Protocol)",
            "class LocalFilesystemArtifactStorage",
            'staging = parent / f".{request.key.version}.staging-',
            "os.rename(staging, final)",
            "def plan_retention",
            "def reconcile",
        ),
        "apps/server/src/nexora/export_storage.py": (
            "class ExportBundlePublisher",
            "partial or unexpected export files are forbidden",
            "ZIP_DEFLATED",
        ),
        "apps/server/src/nexora/composition.py": (
            "artifact_storage: ArtifactStorage | None",
            "LocalFilesystemArtifactStorage",
        ),
        "apps/server/src/nexora/config.py": ('"NEXORA_DEV_DB_PORT"',),
        "apps/server/tests/test_artifact_storage.py": (
            "test_partial_publish_never_becomes_visible",
            "test_retention_is_dry_run_and_never_selects_immutable_or_pinned_evidence",
            "test_partial_mismatched_or_traversing_export_is_rejected",
        ),
        "infra/compose/private-single-host.yml": (
            "NEXORA_ARTIFACT_ROOT: /var/lib/nexora/artifacts",
            "nexora-artifacts:/var/lib/nexora/artifacts",
        ),
        "docs/adr/0024-versioned-artifact-and-export-storage.md": ("Status: Frozen by NEX-P1-10",),
        "docs/v0.1/15-artifact-and-export-storage.md": (
            "NEX-P1-GAP-006",
            CANDIDATE_SHA,
            "40524390732",
            "NEX-P1-11",
        ),
        ".github/workflows/artifact-export-storage.yml": ("Artifact and export storage",),
        "artifacts/p1-10/artifact-export-storage-freeze.json": (CANDIDATE_SHA,),
    }
    for relative, markers in required.items():
        path = ROOT / relative
        _require(path.is_file(), f"missing P1-10 file: {relative}")
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in content, f"missing P1-10 marker in {relative}: {marker}")

    compose = (ROOT / "infra/compose/private-single-host.yml").read_text(encoding="utf-8")
    web_block = compose.split("  web:", 1)[1].split("  api:", 1)[0]
    _require("nexora-artifacts" not in web_block, "artifact volume cannot be mounted into the Web container")
    api_source = (ROOT / "apps/server/src/nexora/api.py").read_text(encoding="utf-8")
    _require("StaticFiles" not in api_source, "artifact root cannot be exposed as static files")


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    _require(record.get("schema_version") == "nexora-artifact-export-storage-freeze-v1", "invalid freeze schema")
    _require(record.get("decision_id") == "NEX-P1-10", "invalid freeze decision ID")
    _require(record.get("repository") == "amirhosseinhamidian/nexora", "freeze repository drift")
    _require(record.get("candidate_commit_sha") == CANDIDATE_SHA, "candidate SHA drift")
    _require(record.get("candidate_commit_message") == CANDIDATE_MESSAGE, "candidate commit message drift")
    _require(record.get("candidate_predecessor_sha") == CANDIDATE_PREDECESSOR, "candidate predecessor drift")

    primary = record.get("github_actions")
    _validate_workflow(
        primary,
        label="artifact and export storage",
        run_id=40524390732,
        expected_jobs={
            "storage_contract": (122259827912, "storage-contract"),
            "backend": (122259827442, "backend"),
            "storage_runtime": (122259827555, "storage-runtime"),
        },
    )
    _require(primary.get("head_branch") == "feature/v0.1-foundation", "primary workflow branch drift")
    required_markers = {
        "storage_contract": (
            "locked_dependencies_installed",
            "p1_09_freeze_prerequisite_passed",
            "storage_contract_verifier_passed",
            "repository_contract_tests_passed",
        ),
        "backend": (
            "locked_dependencies_installed",
            "format_passed",
            "lint_passed",
            "typecheck_passed",
            "non_integration_tests_passed",
        ),
        "storage_runtime": (
            "locked_dependencies_installed",
            "atomic_storage_tests_passed",
            "deterministic_export_tests_passed",
            "private_topology_verifier_passed",
        ),
    }
    for job_name, markers in required_markers.items():
        for marker in markers:
            _require(primary["jobs"][job_name].get(marker) is True, f"{job_name} did not confirm {marker}")

    regression = record.get("regression_workflows")
    _require(isinstance(regression, dict), "regression workflow evidence must be an object")
    expected_regression = {
        "contracts": (
            40524390853,
            {
                "phase_zero_acceptance": (122259827452, "phase-zero-acceptance"),
                "security_boundary": (122259827841, "security-boundary"),
                "integration_contract": (122259827883, "integration-contract"),
                "scope_contract": (122259827941, "scope-contract"),
                "technical_baseline": (122259828009, "technical-baseline"),
            },
        ),
        "trd_bot_adapter": (
            40524390759,
            {
                "backend": (122259827267, "backend"),
                "adapter_contract": (122259827768, "adapter-contract"),
            },
        ),
        "postgresql_schema": (
            40524390897,
            {
                "postgresql_17": (122259827680, "postgresql-17"),
                "backend": (122259827918, "backend"),
                "database_contract": (122259828040, "database-contract"),
            },
        ),
        "application_composition": (
            40524390680,
            {
                "backend": (122259827368, "backend"),
                "composition_contract": (122259827857, "composition-contract"),
            },
        ),
        "phase_one_readiness": (
            40524391011,
            {
                "web": (122259828207, "web"),
                "backend": (122259828408, "backend"),
                "readiness_contract": (122259828875, "readiness-contract"),
            },
        ),
        "durable_jobs_outbox": (
            40524390662,
            {
                "backend": (122259827381, "backend"),
                "durable_contract": (122259827920, "durable-contract"),
                "postgresql_17": (122259828193, "postgresql-17"),
            },
        ),
        "trd_bot_sync_runtime": (
            40524390771,
            {
                "sync_contract": (122259826931, "sync-contract"),
                "backend": (122259827294, "backend"),
                "postgresql_17": (122259827444, "postgresql-17"),
            },
        ),
        "runtime_api_auth": (
            40524390579,
            {
                "cross_language_contract": (122259827874, "cross-language-contract"),
                "postgresql_17": (122259827908, "postgresql-17"),
                "backend": (122259827928, "backend"),
                "runtime_contract": (122259828071, "runtime-contract"),
            },
        ),
        "audit_observability": (
            40524390752,
            {
                "postgresql_17": (122259828059, "postgresql-17"),
                "backend": (122259828558, "backend"),
                "observability_contract": (122259828639, "observability-contract"),
            },
        ),
        "runtime_foundation": (
            40524390580,
            {
                "backend": (122259827332, "backend"),
                "web": (122259827682, "web"),
                "foundation_contract": (122259827683, "foundation-contract"),
            },
        ),
        "single_owner_identity_runtime": (
            40524390929,
            {
                "postgresql_17": (122259827867, "postgresql-17"),
                "backend": (122259827937, "backend"),
                "identity_contract": (122259827944, "identity-contract"),
                "private_topology": (122259828106, "private-topology"),
            },
        ),
    }
    _require(set(regression) == set(expected_regression), "regression workflow inventory mismatch")
    for label, (run_id, jobs) in expected_regression.items():
        _validate_workflow(regression[label], label=label, run_id=run_id, expected_jobs=jobs)

    evidence = record.get("artifact_export_storage_contract")
    _require(isinstance(evidence, dict), "artifact storage contract evidence must be an object")
    _require(evidence.get("schema_version") == contract.get("schema_version"), "contract schema mismatch")
    _require(evidence.get("path") == "contracts/nexora-v0.1-artifact-export-storage.json", "contract path drift")
    _require(evidence.get("checksum") == CONTRACT_CHECKSUM, "recorded contract checksum drift")
    _require(evidence.get("checksum") == canonical_checksum(contract), "contract checksum mismatch")

    prerequisite = record.get("p1_09_prerequisite")
    _require(isinstance(prerequisite, dict), "P1-09 prerequisite must be an object")
    _require(prerequisite.get("decision_id") == "NEX-P1-09", "P1-09 prerequisite decision drift")
    _require(prerequisite.get("frozen") is True, "P1-09 prerequisite is not frozen")
    _require(prerequisite.get("freeze_commit_sha") == P1_09_FREEZE_COMMIT, "P1-09 freeze commit drift")
    _require(
        prerequisite.get("freeze_record_path") == "artifacts/p1-09/trd-bot-sync-runtime-freeze.json",
        "P1-09 path drift",
    )
    _require(
        prerequisite.get("freeze_record_checksum")
        == canonical_checksum(_json(P1_09_FREEZE_PATH))
        == P1_09_FREEZE_CHECKSUM,
        "P1-09 freeze checksum mismatch",
    )

    _require(record.get("recorded_on") == "2026-10-27", "invalid freeze record date")
    _require(record.get("frozen") is True, "P1-10 is not frozen")
    _require(record.get("closed_gaps") == ["NEX-P1-GAP-006"], "frozen gap inventory drift")
    for key in (
        "production_readiness_claimed",
        "public_artifact_access",
        "cloud_storage_credentials",
        "retention_execution_enabled",
        "automatic_evidence_deletion",
        "public_internet_profile",
        "live_execution_capability",
        "exchange_credentials",
        "wallet_capability",
        "autonomous_ai_execution",
    ):
        _require(record.get(key) is False, f"freeze record cannot enable {key}")
    _require(record.get("next_allowed_stage") == "NEX-P1-11", "post-freeze stage drift")


def main() -> int:
    validate_frozen_p1_09()
    contract = load_contract()
    validate_contract(contract)
    validate_files_and_runtime_markers()
    validate_freeze_record(load_freeze_record(), contract)
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_09_PREREQUISITE=PASS")
    print("NEX_P1_10_ARTIFACT_EXPORT_STORAGE=PASS")
    print(f"candidate_commit_sha={CANDIDATE_SHA}")
    print("NEX_P1_10_FREEZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
