from __future__ import annotations

import json
import os
import shutil
import zipfile
from collections import namedtuple
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from nexora.adapters.trd_bot.models import CurrencyUnitContext, ExportFile, ExportManifest
from nexora.artifact_storage import (
    CONTENT_FILENAME,
    MANIFEST_FILENAME,
    ArtifactCapacityExceeded,
    ArtifactConfigurationError,
    ArtifactConflict,
    ArtifactIntegrityError,
    ArtifactKey,
    ArtifactNamespace,
    ArtifactPublishRequest,
    ArtifactQuotaPolicy,
    ArtifactStorageError,
    ArtifactStorageSettings,
    ArtifactValidationError,
    LocalFilesystemArtifactStorage,
    RetentionClass,
    load_artifact_storage_settings,
)
from nexora.export_storage import ExportBundlePublisher

DiskUsage = namedtuple("DiskUsage", "total used free")
OWNER_ID = UUID("926f118d-6943-4d5d-9eb5-a8ec82491fe9")
NOW = datetime(2026, 10, 27, 8, 0, tzinfo=UTC)


def _storage(
    root: Path,
    *,
    quota: ArtifactQuotaPolicy | None = None,
    disk: DiskUsage | None = None,
) -> LocalFilesystemArtifactStorage:
    usage = disk or DiskUsage(10_000_000, 0, 10_000_000)
    return LocalFilesystemArtifactStorage(
        ArtifactStorageSettings(root=root, quota=quota or ArtifactQuotaPolicy(1_000_000, 2_000_000)),
        disk_usage=lambda _: usage,
    )


def _request(
    *,
    namespace: ArtifactNamespace = ArtifactNamespace.EXPORT,
    retention: RetentionClass = RetentionClass.UNPINNED_EXPORT,
    artifact_id: str = "exp_bundle_01JAX72D8C5F3K9M",
    version: str = "v1-fixture",
    published_at: datetime = NOW,
) -> ArtifactPublishRequest:
    return ArtifactPublishRequest(
        key=ArtifactKey(
            owner_id=OWNER_ID,
            namespace=namespace,
            artifact_type="verified-bundle" if namespace is ArtifactNamespace.EXPORT else "source-evidence",
            artifact_id=artifact_id,
            version=version,
        ),
        file_name="bundle.zip" if namespace is ArtifactNamespace.EXPORT else "evidence.json",
        media_type="application/zip" if namespace is ArtifactNamespace.EXPORT else "application/json",
        content_schema_version="fixture-v1",
        retention_class=retention,
        published_at=published_at,
    )


def test_publish_is_atomic_immutable_manifest_backed_and_owner_scoped(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "artifacts")
    request = _request()
    content = b"verified export content"

    manifest = storage.publish_bytes(request, content)
    directory = storage.settings.root.joinpath(*request.key.parts)

    assert storage.read(request.key).content == content
    assert manifest.sha256 == "cd720430a33997278891f510a8cb809bd3fda3e7923693689f88e56c0ef386d5"
    assert json.loads((directory / MANIFEST_FILENAME).read_text())["public_access"] is False
    assert (directory / CONTENT_FILENAME).stat().st_mode & 0o777 == 0o440
    assert (directory / MANIFEST_FILENAME).stat().st_mode & 0o777 == 0o440
    assert list((storage.settings.root / ".staging").iterdir()) == []


def test_identical_retry_is_idempotent_but_changed_content_conflicts(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "artifacts")
    request = _request()
    first = storage.publish_bytes(request, b"same")
    assert storage.publish_bytes(request, b"same") == first
    with pytest.raises(ArtifactConflict):
        storage.publish_bytes(request, b"changed")


def test_partial_publish_never_becomes_visible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _storage(tmp_path / "artifacts")
    original = LocalFilesystemArtifactStorage._write_synced
    calls = 0

    def fail_manifest(path: Path, source: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated interrupted manifest write")
        original(path, source)  # type: ignore[arg-type]

    monkeypatch.setattr(LocalFilesystemArtifactStorage, "_write_synced", staticmethod(fail_manifest))
    with pytest.raises(OSError, match="simulated"):
        storage.publish_bytes(_request(), b"content")

    assert not storage.settings.root.joinpath(*_request().key.parts).exists()
    assert list((storage.settings.root / ".staging").iterdir()) == []


def test_read_and_reconciliation_detect_content_tampering(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "artifacts")
    request = _request()
    storage.publish_bytes(request, b"original")
    content = storage.settings.root.joinpath(*request.key.parts, CONTENT_FILENAME)
    content.chmod(0o600)
    content.write_bytes(b"tampered")

    with pytest.raises(ArtifactIntegrityError, match="checksum"):
        storage.read(request.key)
    report = storage.reconcile()
    assert report.manifest_count == 1
    assert report.verified_count == 0
    assert [issue.code for issue in report.issues] == ["ARTIFACT_INTEGRITY_FAILED"]


@pytest.mark.parametrize("value", ["../escape", "/absolute", "two/parts", "", "bad value"])
def test_artifact_identifiers_reject_path_traversal(value: str) -> None:
    with pytest.raises(ArtifactValidationError):
        ArtifactKey(
            owner_id=OWNER_ID,
            namespace=ArtifactNamespace.EXPORT,
            artifact_type=value,
            artifact_id="artifact-1",
            version="v1",
        )


def test_file_name_must_be_a_safe_basename() -> None:
    request = _request()
    with pytest.raises(ArtifactValidationError, match="basename"):
        ArtifactPublishRequest(
            key=request.key,
            file_name="../secret",
            media_type=request.media_type,
            content_schema_version=request.content_schema_version,
            retention_class=request.retention_class,
            published_at=request.published_at,
        )


def test_symbolic_parent_is_rejected(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "artifacts")
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, storage.settings.root / str(OWNER_ID))
    with pytest.raises(ArtifactStorageError, match="unsafe"):
        storage.publish_bytes(_request(), b"must not escape")
    assert list(outside.iterdir()) == []


def test_noncritical_writes_stop_at_final_threshold_but_immutable_source_can_continue(tmp_path: Path) -> None:
    quota = ArtifactQuotaPolicy(soft_limit_bytes=1_000, hard_limit_bytes=10_000)
    storage = _storage(tmp_path / "artifacts", quota=quota, disk=DiskUsage(100_000, 0, 100_000))
    with pytest.raises(ArtifactCapacityExceeded, match="non-critical"):
        storage.publish_bytes(_request(), b"x" * 1_000)

    source = _request(
        namespace=ArtifactNamespace.SOURCE,
        retention=RetentionClass.IMMUTABLE_SOURCE_EVIDENCE,
        artifact_id="source-1",
    )
    assert storage.publish_bytes(source, b"x" * 1_000).retention_class is RetentionClass.IMMUTABLE_SOURCE_EVIDENCE


def test_hard_quota_and_free_space_reserve_fail_closed(tmp_path: Path) -> None:
    quota = ArtifactQuotaPolicy(soft_limit_bytes=1_000, hard_limit_bytes=1_100)
    hard_limited = _storage(tmp_path / "hard", quota=quota, disk=DiskUsage(100_000, 0, 100_000))
    with pytest.raises(ArtifactCapacityExceeded, match="hard quota"):
        hard_limited.publish_bytes(
            _request(
                namespace=ArtifactNamespace.SOURCE,
                retention=RetentionClass.IMMUTABLE_SOURCE_EVIDENCE,
                artifact_id="source-1",
            ),
            b"x" * 1_100,
        )

    reserve_limited = _storage(
        tmp_path / "reserve",
        quota=ArtifactQuotaPolicy(1_000, 10_000),
        disk=DiskUsage(10_000, 8_500, 1_500),
    )
    with pytest.raises(ArtifactCapacityExceeded, match="free-space"):
        reserve_limited.publish_bytes(_request(), b"x")


def test_retention_is_dry_run_and_never_selects_immutable_or_pinned_evidence(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "artifacts")
    old = NOW - timedelta(days=31)
    storage.publish_bytes(_request(published_at=old), b"expired")
    storage.publish_bytes(
        _request(retention=RetentionClass.PINNED_EXPORT, artifact_id="exp_pinned_01JAX72D8C5F3K9M", published_at=old),
        b"pinned",
    )
    storage.publish_bytes(
        _request(
            namespace=ArtifactNamespace.SOURCE,
            retention=RetentionClass.IMMUTABLE_SOURCE_EVIDENCE,
            artifact_id="source-1",
            published_at=old,
        ),
        b"source",
    )

    report = storage.plan_retention(now=NOW)

    assert report.dry_run is True
    assert [candidate.key.artifact_id for candidate in report.candidates] == ["exp_bundle_01JAX72D8C5F3K9M"]
    assert report.protected_count == 2
    assert report.reclaimable_bytes == len(b"expired")
    assert storage.reconcile().verified_count == 3


def test_reconciliation_reports_orphan_content_and_abandoned_staging(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "artifacts")
    orphan = storage.settings.root / str(uuid4()) / "export" / "type" / "id" / "v1"
    orphan.mkdir(parents=True)
    (orphan / CONTENT_FILENAME).write_bytes(b"orphan")
    (storage.settings.root / ".staging" / "abandoned").mkdir()

    codes = {issue.code for issue in storage.reconcile().issues}

    assert codes == {"ABANDONED_STAGING_ENTRY", "ORPHAN_ARTIFACT_CONTENT"}


def test_storage_configuration_requires_an_absolute_root(tmp_path: Path) -> None:
    assert load_artifact_storage_settings({"NEXORA_ARTIFACT_ROOT": str(tmp_path)}).root == tmp_path
    with pytest.raises(ArtifactConfigurationError, match="required"):
        load_artifact_storage_settings({})
    with pytest.raises(ArtifactConfigurationError, match="absolute"):
        load_artifact_storage_settings({"NEXORA_ARTIFACT_ROOT": "relative"})


def test_generated_export_workspace_stays_inside_private_artifact_root(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "artifacts")
    with storage.temporary_file() as generated:
        assert storage.settings.root in generated.parents
        assert generated.stat().st_mode & 0o777 == 0o600
        generated.write_bytes(b"private export bytes")
    assert not generated.exists()


def _export_manifest(content: bytes, *, path: str = "data/decisions.jsonl") -> ExportManifest:
    return ExportManifest(
        schema_version="nexora-export-manifest-v1",
        export_id="exp_bundle_01JAX72D8C5F3K9M",
        generated_at=NOW,
        mode="selected",
        profile="ai_safe",
        source_versions={"trd_bot": "0.3.1"},
        scope=("decision_evaluation",),
        filters={},
        timezone="UTC",
        currency_unit_context=CurrencyUnitContext(base_currency="USDT", quantity_units_explicit=True),
        lineage_references=(),
        files=(
            ExportFile(
                path=path,
                media_type="application/x-ndjson",
                row_count=1,
                size_bytes=len(content),
                sha256=__import__("hashlib").sha256(content).hexdigest(),
                schema_version="decision-export-v1",
            ),
        ),
        redaction_profile="ai-safe-v1",
        completion_status="complete",
    )


def test_verified_export_bundle_is_deterministic_complete_and_manifest_backed(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "artifacts")
    publisher = ExportBundlePublisher(storage)
    content = b'{"decision_id":"decision-1"}\n'
    manifest = _export_manifest(content)

    first = publisher.publish(
        owner_id=OWNER_ID, manifest=manifest, files={manifest.files[0].path: content}, pinned=False
    )
    second = publisher.publish(
        owner_id=OWNER_ID, manifest=manifest, files={manifest.files[0].path: content}, pinned=False
    )
    stored = storage.read(first.key)

    assert second == first
    assert first.media_type == "application/zip"
    bundle = tmp_path / "bundle.zip"
    bundle.write_bytes(stored.content)
    with zipfile.ZipFile(bundle) as archive:
        assert archive.namelist() == ["manifest.json", "data/decisions.jsonl"]
        assert archive.read("data/decisions.jsonl") == content
        assert json.loads(archive.read("manifest.json"))["completion_status"] == "complete"


def test_partial_mismatched_or_traversing_export_is_rejected(tmp_path: Path) -> None:
    publisher = ExportBundlePublisher(_storage(tmp_path / "artifacts"))
    content = b"one\n"
    manifest = _export_manifest(content)
    with pytest.raises(ArtifactValidationError, match="partial"):
        publisher.publish(owner_id=OWNER_ID, manifest=manifest, files={}, pinned=False)
    with pytest.raises(ArtifactValidationError, match="checksum"):
        publisher.publish(owner_id=OWNER_ID, manifest=manifest, files={manifest.files[0].path: b"two\n"}, pinned=False)
    traversal = _export_manifest(content, path="../escape.jsonl")
    with pytest.raises(ArtifactValidationError, match="unsafe"):
        publisher.publish(owner_id=OWNER_ID, manifest=traversal, files={"../escape.jsonl": content}, pinned=False)


def test_artifact_root_cannot_be_a_symbolic_link(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ArtifactConfigurationError, match="non-symbolic"):
        LocalFilesystemArtifactStorage(ArtifactStorageSettings(linked))


def test_usage_status_uses_bounded_thresholds(tmp_path: Path) -> None:
    storage = _storage(
        tmp_path / "artifacts",
        quota=ArtifactQuotaPolicy(soft_limit_bytes=10_000, hard_limit_bytes=20_000),
        disk=DiskUsage(100_000, 10_000, 90_000),
    )
    storage.publish_bytes(
        _request(
            namespace=ArtifactNamespace.SOURCE,
            retention=RetentionClass.IMMUTABLE_SOURCE_EVIDENCE,
            artifact_id="source-1",
        ),
        b"x" * 7_000,
    )
    assert storage.usage().status in {"warning", "critical"}
    assert storage.usage().free_percent == 90.0


def test_publish_file_rejects_symbolic_sources(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "artifacts")
    actual = tmp_path / "actual.bin"
    actual.write_bytes(b"content")
    linked = tmp_path / "linked.bin"
    linked.symlink_to(actual)
    with pytest.raises(ArtifactValidationError, match="non-symbolic"):
        storage.publish_file(_request(), linked)


def test_default_policy_matches_frozen_private_runtime_budget() -> None:
    quota = ArtifactQuotaPolicy()
    assert quota.soft_limit_bytes == 100 * 1024**3
    assert quota.minimum_free_percent == 20
    assert (quota.warning_percent, quota.critical_percent, quota.write_protect_percent) == (70, 85, 95)
    assert shutil.disk_usage is not None
