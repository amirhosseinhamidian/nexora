from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from nexora.artifact_storage import ArtifactStorageSettings, LocalFilesystemArtifactStorage
from nexora.private_operations import (
    BackupRetentionExecutor,
    JsonLinesOperationsAudit,
    RetentionExecutor,
    capacity_report,
    publish_encrypted_backup,
    verify_backup_copy,
)


def _required_path(environ: Mapping[str, str], name: str) -> Path:
    value = environ.get(name)
    if value is None or not value.strip():
        raise SystemExit(f"{name} is required")
    path = Path(value)
    if not path.is_absolute():
        raise SystemExit(f"{name} must be absolute")
    return path


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include UTC")
    return parsed.astimezone(UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nexora private operations")
    commands = parser.add_subparsers(dest="command", required=True)

    publish = commands.add_parser("publish-backup")
    publish.add_argument("encrypted_bundle", type=Path)
    publish.add_argument("--backup-id", required=True)
    publish.add_argument("--created-at", required=True, type=_utc)

    verify = commands.add_parser("verify-backup")
    verify.add_argument("--backup-id", required=True)
    verify.add_argument("--root", required=True, type=Path)

    retention = commands.add_parser("retention")
    retention.add_argument("--apply", action="store_true")
    retention.add_argument("--now", type=_utc)

    backup_retention = commands.add_parser("backup-retention")
    backup_retention.add_argument("--apply", action="store_true")
    backup_retention.add_argument("--now", type=_utc)

    capacity = commands.add_parser("capacity")
    capacity.add_argument("--database-bytes", type=int, required=True)
    return parser


def main(argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    source = os.environ if environ is None else environ
    if arguments.command == "publish-backup":
        commit_sha = source.get("SOURCE_COMMIT_SHA", "")
        manifest = publish_encrypted_backup(
            arguments.encrypted_bundle,
            backup_id=arguments.backup_id,
            created_at=arguments.created_at,
            source_commit_sha=commit_sha,
            runtime_backup_root=_required_path(source, "NEXORA_BACKUP_ROOT"),
            offsite_backup_root=_required_path(source, "NEXORA_BACKUP_OFFSITE_ROOT"),
        )
        print(manifest.canonical_bytes().decode().strip())
        return 0
    if arguments.command == "verify-backup":
        manifest = verify_backup_copy(arguments.root, arguments.backup_id)
        print(manifest.canonical_bytes().decode().strip())
        return 0

    if arguments.command == "backup-retention":
        backup_executor = BackupRetentionExecutor(
            runtime_backup_root=_required_path(source, "NEXORA_BACKUP_ROOT"),
            offsite_backup_root=_required_path(source, "NEXORA_BACKUP_OFFSITE_ROOT"),
            evidence_root=_required_path(source, "NEXORA_RETENTION_EVIDENCE_ROOT"),
            audit=JsonLinesOperationsAudit(_required_path(source, "NEXORA_OPERATIONS_AUDIT_FILE")),
        )
        backup_result = backup_executor.run(now=arguments.now or datetime.now(UTC), apply=arguments.apply)
        print(
            json.dumps(
                {
                    "schema_version": "nexora-backup-retention-command-result-v1",
                    "execution_id": backup_result.execution_id,
                    "dry_run": backup_result.dry_run,
                    "candidate_count": backup_result.candidate_count,
                    "deleted_count": backup_result.deleted_count,
                    "reclaimed_bytes": backup_result.reclaimed_bytes,
                    "protected_count": backup_result.protected_count,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0

    storage = LocalFilesystemArtifactStorage(
        ArtifactStorageSettings(root=_required_path(source, "NEXORA_ARTIFACT_ROOT"))
    )
    if arguments.command == "retention":
        artifact_executor = RetentionExecutor(
            storage,
            evidence_root=_required_path(source, "NEXORA_RETENTION_EVIDENCE_ROOT"),
            audit=JsonLinesOperationsAudit(_required_path(source, "NEXORA_OPERATIONS_AUDIT_FILE")),
        )
        artifact_result = artifact_executor.run(now=arguments.now or datetime.now(UTC), apply=arguments.apply)
        print(
            json.dumps(
                {
                    "schema_version": "nexora-retention-command-result-v1",
                    "execution_id": artifact_result.execution_id,
                    "dry_run": artifact_result.dry_run,
                    "candidate_count": artifact_result.candidate_count,
                    "deleted_count": artifact_result.deleted_count,
                    "reclaimed_bytes": artifact_result.reclaimed_bytes,
                    "protected_count": artifact_result.protected_count,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    print(json.dumps(capacity_report(storage, database_bytes=arguments.database_bytes), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
