from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Mapping
from pathlib import PurePosixPath
from uuid import UUID

from nexora.adapters.trd_bot.models import ExportManifest
from nexora.artifact_storage import (
    ArtifactKey,
    ArtifactManifest,
    ArtifactNamespace,
    ArtifactPublishRequest,
    ArtifactStorage,
    ArtifactValidationError,
    RetentionClass,
)


def _canonical_json(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _validate_export_path(value: str) -> None:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ArtifactValidationError("export file path is unsafe")
    if "\\" in value or value.startswith("/") or value == "manifest.json" or len(value.encode("utf-8")) > 512:
        raise ArtifactValidationError("export file path is unsafe")


def _zip_entry(name: str) -> zipfile.ZipInfo:
    entry = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.create_system = 3
    entry.external_attr = 0o100440 << 16
    return entry


class ExportBundlePublisher:
    def __init__(self, storage: ArtifactStorage) -> None:
        self._storage = storage

    def publish(
        self,
        *,
        owner_id: UUID,
        manifest: ExportManifest,
        files: Mapping[str, bytes],
        pinned: bool,
    ) -> ArtifactManifest:
        expected = {item.path: item for item in manifest.files}
        if len(expected) != len(manifest.files):
            raise ArtifactValidationError("export manifest contains duplicate file paths")
        if set(files) != set(expected):
            raise ArtifactValidationError("partial or unexpected export files are forbidden")
        for path, descriptor in expected.items():
            _validate_export_path(path)
            content = files[path]
            if len(content) != descriptor.size_bytes:
                raise ArtifactValidationError("export file size does not match the manifest")
            if hashlib.sha256(content).hexdigest() != descriptor.sha256:
                raise ArtifactValidationError("export file checksum does not match the manifest")

        manifest_bytes = _canonical_json(manifest.model_dump(mode="json"))
        manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
        version = f"v1-{manifest_digest[:16]}"
        request = ArtifactPublishRequest(
            key=ArtifactKey(
                owner_id=owner_id,
                namespace=ArtifactNamespace.EXPORT,
                artifact_type="trd-bot-export",
                artifact_id=manifest.export_id,
                version=version,
            ),
            file_name=f"{manifest.export_id}.zip",
            media_type="application/zip",
            content_schema_version="nexora-export-bundle-v1",
            retention_class=RetentionClass.PINNED_EXPORT if pinned else RetentionClass.UNPINNED_EXPORT,
            published_at=manifest.generated_at,
        )
        with self._storage.temporary_file() as bundle:
            with zipfile.ZipFile(bundle, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                archive.writestr(_zip_entry("manifest.json"), manifest_bytes)
                for path in sorted(files):
                    archive.writestr(_zip_entry(path), files[path])
            return self._storage.publish_file(request, bundle)
