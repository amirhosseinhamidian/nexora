from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from nexora.artifact_storage import (
    ArtifactKey,
    ArtifactNamespace,
    ArtifactNotFound,
    ArtifactPublishRequest,
    ArtifactStorageSettings,
    LocalFilesystemArtifactStorage,
    RetentionClass,
)
from nexora.private_operations import (
    BackupRetentionExecutor,
    JsonLinesOperationsAudit,
    PrivateOperationsError,
    RetentionExecutor,
    backup_id,
    capacity_report,
    publish_encrypted_backup,
    verify_backup_copy,
)

NOW = datetime(2026, 10, 28, 0, 0, tzinfo=UTC)
OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
COMMIT_SHA = "6214b79786b0f92d8f06c4c43b3533db717b5ce2"


def _request(
    *,
    namespace: ArtifactNamespace,
    retention: RetentionClass,
    artifact_id: str,
    published_at: datetime,
) -> ArtifactPublishRequest:
    return ArtifactPublishRequest(
        key=ArtifactKey(
            owner_id=OWNER_ID,
            namespace=namespace,
            artifact_type="operations_test",
            artifact_id=artifact_id,
            version="v1",
        ),
        file_name="evidence.json",
        media_type="application/json",
        content_schema_version="operations-test-v1",
        retention_class=retention,
        published_at=published_at,
    )


def test_encrypted_backup_is_atomically_published_to_runtime_and_offsite_roots(tmp_path: Path) -> None:
    encrypted = tmp_path / "generated.age"
    encrypted.write_bytes(b"age-encryption.org/v1\nopaque-ciphertext")
    runtime = tmp_path / "runtime"
    offsite = tmp_path / "offsite"
    identifier = backup_id(NOW, "1a2b3c4d")

    manifest = publish_encrypted_backup(
        encrypted,
        backup_id=identifier,
        created_at=NOW,
        source_commit_sha=COMMIT_SHA,
        runtime_backup_root=runtime,
        offsite_backup_root=offsite,
    )

    assert verify_backup_copy(runtime, identifier) == manifest
    assert verify_backup_copy(offsite, identifier) == manifest
    assert manifest.to_payload()["secrets_included"] is False
    assert manifest.to_payload()["runtime_host_copy_counts_as_offsite"] is False


def test_backup_rejects_plaintext(tmp_path: Path) -> None:
    plaintext = tmp_path / "backup.tar"
    plaintext.write_bytes(b"plaintext")
    root = tmp_path / "backup"

    with pytest.raises(PrivateOperationsError, match="not an age encrypted"):
        publish_encrypted_backup(
            plaintext,
            backup_id=backup_id(NOW, "1a2b3c4d"),
            created_at=NOW,
            source_commit_sha=COMMIT_SHA,
            runtime_backup_root=root,
            offsite_backup_root=root,
        )


def test_backup_rejects_runtime_root_as_offsite_copy(tmp_path: Path) -> None:
    encrypted = tmp_path / "generated.age"
    encrypted.write_bytes(b"age-encryption.org/v1\nopaque-ciphertext")
    root = tmp_path / "backup"

    with pytest.raises(PrivateOperationsError, match="must differ"):
        publish_encrypted_backup(
            encrypted,
            backup_id=backup_id(NOW, "1a2b3c4d"),
            created_at=NOW,
            source_commit_sha=COMMIT_SHA,
            runtime_backup_root=root,
            offsite_backup_root=root,
        )


def test_backup_verification_detects_ciphertext_corruption(tmp_path: Path) -> None:
    encrypted = tmp_path / "generated.age"
    encrypted.write_bytes(b"age-encryption.org/v1\nopaque-ciphertext")
    runtime = tmp_path / "runtime"
    offsite = tmp_path / "offsite"
    identifier = backup_id(NOW, "1a2b3c4d")
    publish_encrypted_backup(
        encrypted,
        backup_id=identifier,
        created_at=NOW,
        source_commit_sha=COMMIT_SHA,
        runtime_backup_root=runtime,
        offsite_backup_root=offsite,
    )
    corrupted = runtime / f"{identifier}.tar.age"
    corrupted.chmod(0o600)
    corrupted.write_bytes(b"corrupt")

    with pytest.raises(PrivateOperationsError, match="checksum mismatch"):
        verify_backup_copy(runtime, identifier)


def test_backup_verification_rejects_path_traversal_identifier(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()

    with pytest.raises(PrivateOperationsError, match="backup ID is invalid"):
        verify_backup_copy(root, "../outside")


def test_retention_dry_run_then_apply_never_deletes_protected_evidence(tmp_path: Path) -> None:
    storage = LocalFilesystemArtifactStorage(ArtifactStorageSettings(root=tmp_path / "artifacts"))
    expired = _request(
        namespace=ArtifactNamespace.EXPORT,
        retention=RetentionClass.UNPINNED_EXPORT,
        artifact_id="expired_export",
        published_at=NOW - timedelta(days=31),
    )
    protected = _request(
        namespace=ArtifactNamespace.SOURCE,
        retention=RetentionClass.IMMUTABLE_SOURCE_EVIDENCE,
        artifact_id="immutable_evidence",
        published_at=NOW - timedelta(days=365),
    )
    storage.publish_bytes(expired, b"expired")
    storage.publish_bytes(protected, b"immutable")
    executor = RetentionExecutor(
        storage,
        evidence_root=tmp_path / "retention-evidence",
        audit=JsonLinesOperationsAudit(tmp_path / "operations-audit.jsonl"),
    )

    dry_run = executor.run(now=NOW)
    assert (dry_run.dry_run, dry_run.candidate_count, dry_run.deleted_count) == (True, 1, 0)
    assert storage.read(expired.key).content == b"expired"

    applied = executor.run(now=NOW, apply=True)
    assert (applied.dry_run, applied.deleted_count, applied.reclaimed_bytes) == (False, 1, 7)
    with pytest.raises(ArtifactNotFound):
        storage.read(expired.key)
    assert storage.read(protected.key).content == b"immutable"
    assert "immutable_evidence" not in (tmp_path / "operations-audit.jsonl").read_text()

    repeated = executor.run(now=NOW, apply=True)
    assert repeated == applied


def test_capacity_report_degrades_without_claiming_evidence_loss(tmp_path: Path) -> None:
    storage = LocalFilesystemArtifactStorage(
        ArtifactStorageSettings(root=tmp_path / "artifacts"),
        disk_usage=lambda _: (200 * 1024**3, 180 * 1024**3, 19 * 1024**3),
    )

    report = capacity_report(storage, database_bytes=21 * 1024**3)

    assert report["degraded"] is True
    assert report["immutable_evidence_dropped"] is False


def test_backup_retention_dry_run_then_apply_removes_both_old_copies(tmp_path: Path) -> None:
    encrypted = tmp_path / "generated.age"
    encrypted.write_bytes(b"age-encryption.org/v1\nopaque-ciphertext")
    runtime = tmp_path / "runtime"
    offsite = tmp_path / "offsite"
    current_id = backup_id(NOW, "11111111")
    old_at = NOW - timedelta(days=400)
    old_id = backup_id(old_at, "22222222")
    for identifier, created_at in ((current_id, NOW), (old_id, old_at)):
        publish_encrypted_backup(
            encrypted,
            backup_id=identifier,
            created_at=created_at,
            source_commit_sha=COMMIT_SHA,
            runtime_backup_root=runtime,
            offsite_backup_root=offsite,
        )
    executor = BackupRetentionExecutor(
        runtime_backup_root=runtime,
        offsite_backup_root=offsite,
        evidence_root=tmp_path / "retention-evidence",
        audit=JsonLinesOperationsAudit(tmp_path / "operations-audit.jsonl"),
    )

    dry_run = executor.run(now=NOW)
    assert (dry_run.candidate_count, dry_run.deleted_count, dry_run.protected_count) == (1, 0, 1)
    assert (runtime / f"{old_id}.tar.age").is_file()
    assert (offsite / f"{old_id}.tar.age").is_file()

    applied = executor.run(now=NOW, apply=True)
    assert (applied.candidate_count, applied.deleted_count, applied.protected_count) == (1, 1, 1)
    assert not (runtime / f"{old_id}.tar.age").exists()
    assert not (offsite / f"{old_id}.tar.age").exists()
    assert (runtime / f"{current_id}.tar.age").is_file()
    assert (offsite / f"{current_id}.tar.age").is_file()
    assert executor.run(now=NOW, apply=True) == applied


def test_backup_retention_fails_closed_when_offsite_inventory_is_missing(tmp_path: Path) -> None:
    encrypted = tmp_path / "generated.age"
    encrypted.write_bytes(b"age-encryption.org/v1\nopaque-ciphertext")
    runtime = tmp_path / "runtime"
    offsite = tmp_path / "offsite"
    identifier = backup_id(NOW, "33333333")
    publish_encrypted_backup(
        encrypted,
        backup_id=identifier,
        created_at=NOW,
        source_commit_sha=COMMIT_SHA,
        runtime_backup_root=runtime,
        offsite_backup_root=offsite,
    )
    missing = offsite / f"{identifier}.tar.age"
    missing.chmod(0o600)
    missing.unlink()
    executor = BackupRetentionExecutor(
        runtime_backup_root=runtime,
        offsite_backup_root=offsite,
        evidence_root=tmp_path / "retention-evidence",
        audit=JsonLinesOperationsAudit(tmp_path / "operations-audit.jsonl"),
    )

    with pytest.raises(PrivateOperationsError, match="backup file cannot be read"):
        executor.run(now=NOW, apply=True)
