from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, BinaryIO, Final, Protocol
from uuid import UUID, uuid4

ARTIFACT_MANIFEST_SCHEMA: Final = "nexora-artifact-manifest-v1"
ARTIFACT_ROOT_ENV: Final = "NEXORA_ARTIFACT_ROOT"
CONTENT_FILENAME: Final = "content.bin"
MANIFEST_FILENAME: Final = "manifest.json"
GIB: Final = 1024**3
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ArtifactStorageError(RuntimeError):
    """Base error for fail-closed artifact persistence."""


class ArtifactConfigurationError(ArtifactStorageError):
    pass


class ArtifactValidationError(ArtifactStorageError):
    pass


class ArtifactConflict(ArtifactStorageError):
    pass


class ArtifactIntegrityError(ArtifactStorageError):
    pass


class ArtifactNotFound(ArtifactStorageError):
    pass


class ArtifactCapacityExceeded(ArtifactStorageError):
    pass


class ArtifactNamespace(StrEnum):
    SOURCE = "source"
    EXPORT = "export"
    BACKUP = "backup"


class RetentionClass(StrEnum):
    IMMUTABLE_SOURCE_EVIDENCE = "immutable_source_evidence"
    FINANCIAL_RECORD = "financial_record"
    PINNED_EXPORT = "pinned_export"
    UNPINNED_EXPORT = "unpinned_export"
    BACKUP = "backup"


@dataclass(frozen=True, slots=True)
class ArtifactKey:
    owner_id: UUID
    namespace: ArtifactNamespace
    artifact_type: str
    artifact_id: str
    version: str

    def __post_init__(self) -> None:
        for label, value, pattern in (
            ("artifact type", self.artifact_type, IDENTIFIER),
            ("artifact ID", self.artifact_id, IDENTIFIER),
            ("artifact version", self.version, VERSION),
        ):
            if pattern.fullmatch(value) is None:
                raise ArtifactValidationError(f"{label} is invalid")

    @property
    def parts(self) -> tuple[str, ...]:
        return (
            str(self.owner_id),
            self.namespace.value,
            self.artifact_type,
            self.artifact_id,
            self.version,
        )

    @property
    def relative_directory(self) -> Path:
        return Path(*self.parts)


@dataclass(frozen=True, slots=True)
class ArtifactPublishRequest:
    key: ArtifactKey
    file_name: str
    media_type: str
    content_schema_version: str
    retention_class: RetentionClass
    published_at: datetime

    def __post_init__(self) -> None:
        if Path(self.file_name).name != self.file_name or self.file_name in {".", ".."}:
            raise ArtifactValidationError("artifact file name must be a safe basename")
        if (
            not self.file_name
            or len(self.file_name.encode("utf-8")) > 255
            or any(character in self.file_name for character in "\r\n\0")
        ):
            raise ArtifactValidationError("artifact file name is invalid")
        if not self.media_type or any(character in self.media_type for character in "\r\n\0"):
            raise ArtifactValidationError("artifact media type is invalid")
        if IDENTIFIER.fullmatch(self.content_schema_version) is None:
            raise ArtifactValidationError("artifact content schema version is invalid")
        if self.published_at.tzinfo is None or self.published_at.utcoffset() != timedelta(0):
            raise ArtifactValidationError("artifact published_at must be timezone-aware UTC")
        allowed = {
            ArtifactNamespace.SOURCE: {
                RetentionClass.IMMUTABLE_SOURCE_EVIDENCE,
                RetentionClass.FINANCIAL_RECORD,
            },
            ArtifactNamespace.EXPORT: {
                RetentionClass.PINNED_EXPORT,
                RetentionClass.UNPINNED_EXPORT,
            },
            ArtifactNamespace.BACKUP: {RetentionClass.BACKUP},
        }
        if self.retention_class not in allowed[self.key.namespace]:
            raise ArtifactValidationError("artifact namespace and retention class do not match")


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ArtifactIntegrityError("artifact manifest timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ArtifactIntegrityError("artifact manifest timestamp is invalid") from error
    if parsed.utcoffset() != timedelta(0):
        raise ArtifactIntegrityError("artifact manifest timestamp is not UTC")
    return parsed


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    key: ArtifactKey
    file_name: str
    media_type: str
    content_schema_version: str
    size_bytes: int
    sha256: str
    retention_class: RetentionClass
    published_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": ARTIFACT_MANIFEST_SCHEMA,
            "owner_id": str(self.key.owner_id),
            "namespace": self.key.namespace.value,
            "artifact_type": self.key.artifact_type,
            "artifact_id": self.key.artifact_id,
            "version": self.key.version,
            "file_name": self.file_name,
            "media_type": self.media_type,
            "content_schema_version": self.content_schema_version,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "retention_class": self.retention_class.value,
            "published_at": _utc_text(self.published_at),
            "immutable": True,
            "public_access": False,
        }

    def canonical_bytes(self) -> bytes:
        return (json.dumps(self.to_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )

    @classmethod
    def from_payload(cls, payload: object) -> ArtifactManifest:
        if not isinstance(payload, dict):
            raise ArtifactIntegrityError("artifact manifest must be an object")
        expected = {
            "schema_version",
            "owner_id",
            "namespace",
            "artifact_type",
            "artifact_id",
            "version",
            "file_name",
            "media_type",
            "content_schema_version",
            "size_bytes",
            "sha256",
            "retention_class",
            "published_at",
            "immutable",
            "public_access",
        }
        if set(payload) != expected or payload.get("schema_version") != ARTIFACT_MANIFEST_SCHEMA:
            raise ArtifactIntegrityError("artifact manifest schema is invalid")
        if payload.get("immutable") is not True or payload.get("public_access") is not False:
            raise ArtifactIntegrityError("artifact manifest security boundary is invalid")
        size = payload.get("size_bytes")
        digest = payload.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ArtifactIntegrityError("artifact manifest size is invalid")
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
            raise ArtifactIntegrityError("artifact manifest checksum is invalid")
        for field in (
            "owner_id",
            "namespace",
            "artifact_type",
            "artifact_id",
            "version",
            "file_name",
            "media_type",
            "content_schema_version",
            "retention_class",
            "published_at",
        ):
            if not isinstance(payload.get(field), str):
                raise ArtifactIntegrityError("artifact manifest fields are invalid")
        try:
            key = ArtifactKey(
                owner_id=UUID(str(payload["owner_id"])),
                namespace=ArtifactNamespace(str(payload["namespace"])),
                artifact_type=str(payload["artifact_type"]),
                artifact_id=str(payload["artifact_id"]),
                version=str(payload["version"]),
            )
            request = ArtifactPublishRequest(
                key=key,
                file_name=str(payload["file_name"]),
                media_type=str(payload["media_type"]),
                content_schema_version=str(payload["content_schema_version"]),
                retention_class=RetentionClass(str(payload["retention_class"])),
                published_at=_parse_utc(payload["published_at"]),
            )
        except (KeyError, ValueError, ArtifactValidationError) as error:
            raise ArtifactIntegrityError("artifact manifest fields are invalid") from error
        return cls(
            key=request.key,
            file_name=request.file_name,
            media_type=request.media_type,
            content_schema_version=request.content_schema_version,
            size_bytes=size,
            sha256=digest,
            retention_class=request.retention_class,
            published_at=request.published_at,
        )


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    manifest: ArtifactManifest
    content: bytes


@dataclass(frozen=True, slots=True)
class ArtifactQuotaPolicy:
    soft_limit_bytes: int = 100 * GIB
    hard_limit_bytes: int = 160 * GIB
    minimum_free_percent: int = 20
    warning_percent: int = 70
    critical_percent: int = 85
    write_protect_percent: int = 95

    def __post_init__(self) -> None:
        if not 0 < self.soft_limit_bytes <= self.hard_limit_bytes:
            raise ArtifactConfigurationError("artifact quota byte limits are invalid")
        thresholds = (self.warning_percent, self.critical_percent, self.write_protect_percent)
        if not 0 < thresholds[0] < thresholds[1] < thresholds[2] <= 100:
            raise ArtifactConfigurationError("artifact quota thresholds are invalid")
        if not 1 <= self.minimum_free_percent <= 99:
            raise ArtifactConfigurationError("artifact free-space reserve is invalid")


@dataclass(frozen=True, slots=True)
class ArtifactStorageSettings:
    root: Path
    quota: ArtifactQuotaPolicy = ArtifactQuotaPolicy()

    def __post_init__(self) -> None:
        if not self.root.is_absolute():
            raise ArtifactConfigurationError("artifact root must be absolute")


@dataclass(frozen=True, slots=True)
class StorageUsage:
    allocated_bytes: int
    soft_limit_bytes: int
    hard_limit_bytes: int
    filesystem_total_bytes: int
    filesystem_free_bytes: int
    free_percent: float
    status: str


@dataclass(frozen=True, slots=True)
class ReconciliationIssue:
    code: str
    relative_path: str


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    manifest_count: int
    verified_count: int
    allocated_bytes: int
    issues: tuple[ReconciliationIssue, ...]


@dataclass(frozen=True, slots=True)
class RetentionCandidate:
    key: ArtifactKey
    size_bytes: int
    reason_code: str


@dataclass(frozen=True, slots=True)
class RetentionDryRun:
    generated_at: datetime
    cutoff: datetime
    candidates: tuple[RetentionCandidate, ...]
    protected_count: int
    reclaimable_bytes: int
    dry_run: bool = True


class ArtifactStorage(Protocol):
    def publish_bytes(self, request: ArtifactPublishRequest, content: bytes) -> ArtifactManifest: ...

    def publish_file(self, request: ArtifactPublishRequest, source: Path) -> ArtifactManifest: ...

    def temporary_file(self) -> AbstractContextManager[Path]: ...

    def read(self, key: ArtifactKey) -> StoredArtifact: ...

    def reconcile(self) -> ReconciliationReport: ...

    def plan_retention(self, *, now: datetime) -> RetentionDryRun: ...


def load_artifact_storage_settings(environ: Mapping[str, str]) -> ArtifactStorageSettings:
    value = environ.get(ARTIFACT_ROOT_ENV)
    if value is None or not value.strip():
        raise ArtifactConfigurationError(f"{ARTIFACT_ROOT_ENV} is required")
    root = Path(value)
    if not root.is_absolute():
        raise ArtifactConfigurationError("artifact root must be absolute")
    return ArtifactStorageSettings(root=root)


def _sha256_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
    except OSError as error:
        raise ArtifactIntegrityError("artifact content cannot be read") from error
    return size, digest.hexdigest()


def _is_staging_path(path: Path) -> bool:
    return any(part == ".staging" or ".staging-" in part for part in path.parts)


class LocalFilesystemArtifactStorage:
    def __init__(
        self,
        settings: ArtifactStorageSettings,
        *,
        disk_usage: Callable[[str | os.PathLike[str]], tuple[int, int, int]] = shutil.disk_usage,
    ) -> None:
        self.settings = settings
        self._root = settings.root
        self._disk_usage = disk_usage
        self._initialize_root()

    def _initialize_root(self) -> None:
        try:
            self._root.mkdir(parents=True, mode=0o700, exist_ok=True)
            status = self._root.lstat()
        except OSError as error:
            raise ArtifactConfigurationError("artifact root is unavailable") from error
        if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode):
            raise ArtifactConfigurationError("artifact root must be a non-symbolic directory")
        staging = self._root / ".staging"
        staging.mkdir(mode=0o700, exist_ok=True)
        if staging.is_symlink() or not staging.is_dir():
            raise ArtifactConfigurationError("artifact staging root is unsafe")

    def _path(self, key: ArtifactKey) -> Path:
        return self._root.joinpath(*key.parts)

    def _ensure_parent_chain(self, key: ArtifactKey) -> Path:
        current = self._root
        for component in key.parts[:-1]:
            current = current / component
            try:
                current.mkdir(mode=0o700, exist_ok=True)
                status = current.lstat()
            except OSError as error:
                raise ArtifactStorageError("artifact parent directory is unavailable") from error
            if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode):
                raise ArtifactStorageError("artifact parent directory is unsafe")
        return current

    @staticmethod
    def _write_synced(path: Path, source: BinaryIO) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
        finally:
            os.close(descriptor)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _allocated_bytes(self) -> int:
        total = 0
        for path in self._root.rglob("*"):
            if _is_staging_path(path.relative_to(self._root)) or path.is_symlink():
                continue
            try:
                if path.is_file():
                    total += path.stat().st_size
            except OSError:
                continue
        return total

    def usage(self) -> StorageUsage:
        allocated = self._allocated_bytes()
        disk_total, _, disk_free = self._disk_usage(self._root)
        free_percent = 100.0 * disk_free / disk_total if disk_total else 0.0
        used_percent = 100.0 * allocated / self.settings.quota.soft_limit_bytes
        if used_percent >= self.settings.quota.write_protect_percent:
            status = "write_protect_noncritical"
        elif used_percent >= self.settings.quota.critical_percent:
            status = "critical"
        elif used_percent >= self.settings.quota.warning_percent:
            status = "warning"
        else:
            status = "healthy"
        return StorageUsage(
            allocated_bytes=allocated,
            soft_limit_bytes=self.settings.quota.soft_limit_bytes,
            hard_limit_bytes=self.settings.quota.hard_limit_bytes,
            filesystem_total_bytes=disk_total,
            filesystem_free_bytes=disk_free,
            free_percent=free_percent,
            status=status,
        )

    def _check_capacity(self, required_bytes: int, retention_class: RetentionClass) -> None:
        usage = self.usage()
        projected = usage.allocated_bytes + required_bytes
        if projected > self.settings.quota.hard_limit_bytes:
            raise ArtifactCapacityExceeded("artifact hard quota would be exceeded")
        projected_free = usage.filesystem_free_bytes - required_bytes
        free_percent = 100.0 * projected_free / usage.filesystem_total_bytes if usage.filesystem_total_bytes else 0.0
        if free_percent < self.settings.quota.minimum_free_percent:
            raise ArtifactCapacityExceeded("artifact filesystem free-space reserve would be violated")
        critical = retention_class in {
            RetentionClass.IMMUTABLE_SOURCE_EVIDENCE,
            RetentionClass.FINANCIAL_RECORD,
            RetentionClass.BACKUP,
        }
        soft_percent = 100.0 * projected / self.settings.quota.soft_limit_bytes
        if not critical and soft_percent >= self.settings.quota.write_protect_percent:
            raise ArtifactCapacityExceeded("non-critical artifact writes are protected at the final threshold")

    def publish_bytes(self, request: ArtifactPublishRequest, content: bytes) -> ArtifactManifest:
        from io import BytesIO

        digest = hashlib.sha256(content).hexdigest()
        return self._publish(request, BytesIO(content), size_bytes=len(content), sha256=digest)

    def publish_file(self, request: ArtifactPublishRequest, source: Path) -> ArtifactManifest:
        try:
            status = source.lstat()
        except OSError as error:
            raise ArtifactValidationError("artifact source file is unavailable") from error
        if stat.S_ISLNK(status.st_mode) or not stat.S_ISREG(status.st_mode):
            raise ArtifactValidationError("artifact source must be a regular non-symbolic file")
        size, digest = _sha256_file(source)
        with source.open("rb") as stream:
            return self._publish(request, stream, size_bytes=size, sha256=digest)

    @contextmanager
    def temporary_file(self) -> Iterator[Path]:
        staging_root = self._root / ".staging"
        descriptor, raw_path = tempfile.mkstemp(prefix="generated-", dir=staging_root)
        path = Path(raw_path)
        try:
            os.fchmod(descriptor, 0o600)
            os.close(descriptor)
            descriptor = -1
            yield path
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                raise ArtifactStorageError("artifact temporary file cleanup failed") from error

    def _publish(
        self,
        request: ArtifactPublishRequest,
        source: BinaryIO,
        *,
        size_bytes: int,
        sha256: str,
    ) -> ArtifactManifest:
        manifest = ArtifactManifest(
            key=request.key,
            file_name=request.file_name,
            media_type=request.media_type,
            content_schema_version=request.content_schema_version,
            size_bytes=size_bytes,
            sha256=sha256,
            retention_class=request.retention_class,
            published_at=request.published_at,
        )
        manifest_bytes = manifest.canonical_bytes()
        final = self._path(request.key)
        if final.exists():
            existing = self._load_manifest(final / MANIFEST_FILENAME)
            if existing == manifest:
                return existing
            raise ArtifactConflict("artifact version already exists with different immutable content")
        self._check_capacity(size_bytes + len(manifest_bytes), request.retention_class)
        parent = self._ensure_parent_chain(request.key)
        staging = parent / f".{request.key.version}.staging-{uuid4()}"
        try:
            staging.mkdir(mode=0o700)
            content_path = staging / CONTENT_FILENAME
            self._write_synced(content_path, source)
            actual_size, actual_digest = _sha256_file(content_path)
            if (actual_size, actual_digest) != (size_bytes, sha256):
                raise ArtifactIntegrityError("artifact source changed while it was being published")
            from io import BytesIO

            self._write_synced(staging / MANIFEST_FILENAME, BytesIO(manifest_bytes))
            content_path.chmod(0o440)
            (staging / MANIFEST_FILENAME).chmod(0o440)
            self._fsync_directory(staging)
            try:
                os.rename(staging, final)
            except FileExistsError as error:
                raise ArtifactConflict("artifact version was published concurrently") from error
            except OSError as error:
                if final.exists():
                    raise ArtifactConflict("artifact version was published concurrently") from error
                raise ArtifactStorageError("artifact atomic publish failed") from error
            final.chmod(0o550)
            self._fsync_directory(parent)
            return manifest
        finally:
            if staging.exists():
                staging.chmod(0o700)
                shutil.rmtree(staging)

    @staticmethod
    def _load_manifest(path: Path) -> ArtifactManifest:
        try:
            status = path.lstat()
            if stat.S_ISLNK(status.st_mode) or not stat.S_ISREG(status.st_mode):
                raise ArtifactIntegrityError("artifact manifest path is unsafe")
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ArtifactIntegrityError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ArtifactIntegrityError("artifact manifest cannot be read") from error
        return ArtifactManifest.from_payload(payload)

    def read(self, key: ArtifactKey) -> StoredArtifact:
        directory = self._path(key)
        try:
            status = directory.lstat()
        except FileNotFoundError as error:
            raise ArtifactNotFound("artifact version is unavailable") from error
        except OSError as error:
            raise ArtifactIntegrityError("artifact version is unavailable") from error
        if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode):
            raise ArtifactIntegrityError("artifact version path is unsafe")
        manifest = self._load_manifest(directory / MANIFEST_FILENAME)
        if manifest.key != key:
            raise ArtifactIntegrityError("artifact path and manifest identity disagree")
        content_path = directory / CONTENT_FILENAME
        try:
            content_status = content_path.lstat()
            if stat.S_ISLNK(content_status.st_mode) or not stat.S_ISREG(content_status.st_mode):
                raise ArtifactIntegrityError("artifact content path is unsafe")
            content = content_path.read_bytes()
        except ArtifactIntegrityError:
            raise
        except OSError as error:
            raise ArtifactIntegrityError("artifact content cannot be read") from error
        if len(content) != manifest.size_bytes or hashlib.sha256(content).hexdigest() != manifest.sha256:
            raise ArtifactIntegrityError("artifact content checksum mismatch")
        return StoredArtifact(manifest=manifest, content=content)

    def _manifest_paths(self) -> tuple[Path, ...]:
        return tuple(
            sorted(
                path
                for path in self._root.rglob(MANIFEST_FILENAME)
                if not _is_staging_path(path.relative_to(self._root))
            )
        )

    def reconcile(self) -> ReconciliationReport:
        issues: list[ReconciliationIssue] = []
        verified = 0
        allocated = self._allocated_bytes()
        manifests = self._manifest_paths()
        for path in manifests:
            relative = path.relative_to(self._root).as_posix()
            try:
                manifest = self._load_manifest(path)
                if path.parent.relative_to(self._root).parts != manifest.key.parts:
                    raise ArtifactIntegrityError("artifact path and manifest identity disagree")
                stored = self.read(manifest.key)
                if stored.manifest != manifest:
                    raise ArtifactIntegrityError("artifact manifest changed during reconciliation")
                verified += 1
            except ArtifactStorageError:
                issues.append(ReconciliationIssue(code="ARTIFACT_INTEGRITY_FAILED", relative_path=relative))
        for path in self._root.rglob(CONTENT_FILENAME):
            if _is_staging_path(path.relative_to(self._root)):
                continue
            if not (path.parent / MANIFEST_FILENAME).is_file():
                issues.append(
                    ReconciliationIssue(
                        code="ORPHAN_ARTIFACT_CONTENT",
                        relative_path=path.relative_to(self._root).as_posix(),
                    )
                )
        for path in self._root.rglob("*"):
            relative_path = path.relative_to(self._root)
            if _is_staging_path(relative_path):
                continue
            if path.is_symlink():
                issues.append(ReconciliationIssue(code="SYMLINK_ENTRY", relative_path=relative_path.as_posix()))
            elif path.is_file() and path.name not in {CONTENT_FILENAME, MANIFEST_FILENAME}:
                issues.append(ReconciliationIssue(code="UNKNOWN_ARTIFACT_FILE", relative_path=relative_path.as_posix()))
        staging = self._root / ".staging"
        for path in sorted(staging.iterdir()):
            issues.append(
                ReconciliationIssue(
                    code="ABANDONED_STAGING_ENTRY",
                    relative_path=path.relative_to(self._root).as_posix(),
                )
            )
        for path in sorted(self._root.rglob("*.staging-*")):
            issues.append(
                ReconciliationIssue(
                    code="ABANDONED_STAGING_ENTRY",
                    relative_path=path.relative_to(self._root).as_posix(),
                )
            )
        return ReconciliationReport(
            manifest_count=len(manifests),
            verified_count=verified,
            allocated_bytes=allocated,
            issues=tuple(sorted(issues, key=lambda item: (item.code, item.relative_path))),
        )

    def plan_retention(self, *, now: datetime) -> RetentionDryRun:
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ArtifactValidationError("retention time must be timezone-aware UTC")
        cutoff = now - timedelta(days=30)
        candidates: list[RetentionCandidate] = []
        protected = 0
        for path in self._manifest_paths():
            try:
                manifest = self._load_manifest(path)
            except ArtifactStorageError:
                protected += 1
                continue
            if manifest.retention_class is RetentionClass.UNPINNED_EXPORT and manifest.published_at <= cutoff:
                candidates.append(
                    RetentionCandidate(
                        key=manifest.key,
                        size_bytes=manifest.size_bytes,
                        reason_code="UNPINNED_EXPORT_EXPIRED_30_DAYS",
                    )
                )
            else:
                protected += 1
        candidates.sort(key=lambda item: item.key.parts)
        return RetentionDryRun(
            generated_at=now,
            cutoff=cutoff,
            candidates=tuple(candidates),
            protected_count=protected,
            reclaimable_bytes=sum(item.size_bytes for item in candidates),
        )
