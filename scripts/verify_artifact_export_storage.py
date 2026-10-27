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
CONTRACT_CHECKSUM = "a0badfe42b047b4e69089fbc02425d8a1c51d70465148418948835d95ccdd694"
P1_09_FREEZE_CHECKSUM = "5b29d6bc22652acc2576f9027a8eb362c41303f8ecfffaf692ba1bcccdcaec9d"
P1_09_FREEZE_COMMIT = "e3d724074b8ac276f68ebf5d3e100c86a711f672"


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
        "docs/adr/0024-versioned-artifact-and-export-storage.md": ("Status: Candidate for NEX-P1-10",),
        "docs/v0.1/15-artifact-and-export-storage.md": ("NEX-P1-GAP-006", "NEX-P1-11"),
        ".github/workflows/artifact-export-storage.yml": ("Artifact and export storage",),
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


def main() -> int:
    validate_frozen_p1_09()
    contract = load_contract()
    validate_contract(contract)
    validate_files_and_runtime_markers()
    print(f"schema_version={contract['schema_version']}")
    print(f"decision_id={contract['decision_id']}")
    print(f"contract_checksum={canonical_checksum(contract)}")
    print("NEX_P1_09_PREREQUISITE=PASS")
    print("NEX_P1_10_ARTIFACT_EXPORT_STORAGE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
