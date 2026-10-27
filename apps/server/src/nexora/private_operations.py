from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final, Protocol
from uuid import uuid4

from nexora.artifact_storage import ArtifactStorage

BACKUP_MANIFEST_SCHEMA: Final = "nexora-encrypted-backup-manifest-v1"
BACKUP_RETENTION_PLAN_SCHEMA: Final = "nexora-backup-retention-plan-v1"
BACKUP_RETENTION_RESULT_SCHEMA: Final = "nexora-backup-retention-result-v1"
RETENTION_PLAN_SCHEMA: Final = "nexora-retention-plan-v1"
RETENTION_RESULT_SCHEMA: Final = "nexora-retention-result-v1"
BACKUP_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
AGE_HEADER = b"age-encryption.org/v1\n"


class PrivateOperationsError(RuntimeError):
    pass


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise PrivateOperationsError("operation timestamp must be timezone-aware UTC")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _require_safe_directory(path: Path, label: str) -> None:
    if not path.is_absolute():
        raise PrivateOperationsError(f"{label} must be absolute")
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    status = path.lstat()
    if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode):
        raise PrivateOperationsError(f"{label} must be a non-symbolic directory")


def _write_atomic(path: Path, content: bytes, *, mode: int = 0o440) -> None:
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True, slots=True)
class EncryptedBackupManifest:
    backup_id: str
    created_at: datetime
    source_commit_sha: str
    encrypted_file: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if BACKUP_ID.fullmatch(self.backup_id) is None:
            raise PrivateOperationsError("backup ID is invalid")
        _utc_text(self.created_at)
        if re.fullmatch(r"[0-9a-f]{40}", self.source_commit_sha) is None:
            raise PrivateOperationsError("backup source commit SHA is invalid")
        if self.encrypted_file != f"{self.backup_id}.tar.age":
            raise PrivateOperationsError("encrypted backup file name is invalid")
        if self.size_bytes < 1 or SHA256.fullmatch(self.sha256) is None:
            raise PrivateOperationsError("encrypted backup identity is invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": BACKUP_MANIFEST_SCHEMA,
            "backup_id": self.backup_id,
            "created_at": _utc_text(self.created_at),
            "source_commit_sha": self.source_commit_sha,
            "encrypted_file": self.encrypted_file,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "encryption": "age_x25519_offline_recipient",
            "database_included": True,
            "artifacts_included": True,
            "secrets_included": False,
            "sessions_reusable_after_restore": False,
            "service_tokens_reusable_after_restore": False,
            "runtime_host_copy_counts_as_offsite": False,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_payload())

    @classmethod
    def from_payload(cls, payload: object) -> EncryptedBackupManifest:
        if not isinstance(payload, dict):
            raise PrivateOperationsError("backup manifest must be an object")
        expected = {
            "schema_version",
            "backup_id",
            "created_at",
            "source_commit_sha",
            "encrypted_file",
            "size_bytes",
            "sha256",
            "encryption",
            "database_included",
            "artifacts_included",
            "secrets_included",
            "sessions_reusable_after_restore",
            "service_tokens_reusable_after_restore",
            "runtime_host_copy_counts_as_offsite",
        }
        if set(payload) != expected or payload.get("schema_version") != BACKUP_MANIFEST_SCHEMA:
            raise PrivateOperationsError("backup manifest schema is invalid")
        if payload.get("encryption") != "age_x25519_offline_recipient":
            raise PrivateOperationsError("backup encryption profile is invalid")
        required_true = ("database_included", "artifacts_included")
        required_false = (
            "secrets_included",
            "sessions_reusable_after_restore",
            "service_tokens_reusable_after_restore",
            "runtime_host_copy_counts_as_offsite",
        )
        if any(payload.get(key) is not True for key in required_true):
            raise PrivateOperationsError("backup content inventory is incomplete")
        if any(payload.get(key) is not False for key in required_false):
            raise PrivateOperationsError("backup security boundary is invalid")
        try:
            created_at = datetime.fromisoformat(str(payload["created_at"]).replace("Z", "+00:00"))
            return cls(
                backup_id=str(payload["backup_id"]),
                created_at=created_at,
                source_commit_sha=str(payload["source_commit_sha"]),
                encrypted_file=str(payload["encrypted_file"]),
                size_bytes=int(payload["size_bytes"]),
                sha256=str(payload["sha256"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PrivateOperationsError("backup manifest fields are invalid") from error


def publish_encrypted_backup(
    encrypted_bundle: Path,
    *,
    backup_id: str,
    created_at: datetime,
    source_commit_sha: str,
    runtime_backup_root: Path,
    offsite_backup_root: Path,
) -> EncryptedBackupManifest:
    try:
        status = encrypted_bundle.lstat()
    except OSError as error:
        raise PrivateOperationsError("encrypted backup bundle is unavailable") from error
    if stat.S_ISLNK(status.st_mode) or not stat.S_ISREG(status.st_mode):
        raise PrivateOperationsError("encrypted backup bundle must be a regular file")
    with encrypted_bundle.open("rb") as stream:
        if stream.read(len(AGE_HEADER)) != AGE_HEADER:
            raise PrivateOperationsError("backup bundle is not an age encrypted file")
    _require_safe_directory(runtime_backup_root, "runtime backup root")
    _require_safe_directory(offsite_backup_root, "offsite backup root")
    if runtime_backup_root.resolve() == offsite_backup_root.resolve():
        raise PrivateOperationsError("offsite backup root must differ from the runtime backup root")
    size, digest = _sha256_file(encrypted_bundle)
    manifest = EncryptedBackupManifest(
        backup_id=backup_id,
        created_at=created_at,
        source_commit_sha=source_commit_sha,
        encrypted_file=f"{backup_id}.tar.age",
        size_bytes=size,
        sha256=digest,
    )
    for root in (runtime_backup_root, offsite_backup_root):
        target = root / manifest.encrypted_file
        if target.exists() or (root / f"{backup_id}.manifest.json").exists():
            raise PrivateOperationsError("backup ID already exists")
        with encrypted_bundle.open("rb") as source:
            descriptor, raw = tempfile.mkstemp(prefix=f".{target.name}.", dir=root)
            temporary = Path(raw)
            try:
                with os.fdopen(descriptor, "wb") as output:
                    shutil.copyfileobj(source, output)
                    output.flush()
                    os.fsync(output.fileno())
                temporary.chmod(0o440)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        _write_atomic(root / f"{backup_id}.manifest.json", manifest.canonical_bytes())
    return manifest


def verify_backup_copy(root: Path, backup_id: str) -> EncryptedBackupManifest:
    _require_safe_directory(root, "backup root")
    if BACKUP_ID.fullmatch(backup_id) is None:
        raise PrivateOperationsError("backup ID is invalid")
    manifest_path = root / f"{backup_id}.manifest.json"
    try:
        manifest_status = manifest_path.lstat()
        if stat.S_ISLNK(manifest_status.st_mode) or not stat.S_ISREG(manifest_status.st_mode):
            raise PrivateOperationsError("backup manifest path is unsafe")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except PrivateOperationsError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PrivateOperationsError("backup manifest cannot be read") from error
    manifest = EncryptedBackupManifest.from_payload(payload)
    try:
        encrypted_path = root / manifest.encrypted_file
        encrypted_status = encrypted_path.lstat()
        if stat.S_ISLNK(encrypted_status.st_mode) or not stat.S_ISREG(encrypted_status.st_mode):
            raise PrivateOperationsError("encrypted backup path is unsafe")
        size, digest = _sha256_file(encrypted_path)
    except PrivateOperationsError:
        raise
    except OSError as error:
        raise PrivateOperationsError("encrypted backup file cannot be read") from error
    if (size, digest) != (manifest.size_bytes, manifest.sha256):
        raise PrivateOperationsError("encrypted backup checksum mismatch")
    return manifest


class OperationsAuditSink(Protocol):
    def append(self, payload: Mapping[str, object]) -> None: ...


class JsonLinesOperationsAudit:
    def __init__(self, path: Path) -> None:
        if not path.is_absolute():
            raise PrivateOperationsError("operations audit path must be absolute")
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.path = path

    def append(self, payload: Mapping[str, object]) -> None:
        forbidden = ("secret", "password", "token", "credential", "private_key")
        if any(any(part in key.lower() for part in forbidden) for key in payload):
            raise PrivateOperationsError("secret-bearing operations audit field is forbidden")
        encoded = _canonical_bytes(payload)
        descriptor = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


@dataclass(frozen=True, slots=True)
class RetentionExecutionResult:
    execution_id: str
    dry_run: bool
    candidate_count: int
    deleted_count: int
    reclaimed_bytes: int
    protected_count: int
    plan_path: Path
    result_path: Path | None


class RetentionExecutor:
    def __init__(self, storage: ArtifactStorage, *, evidence_root: Path, audit: OperationsAuditSink) -> None:
        _require_safe_directory(evidence_root, "retention evidence root")
        self.storage = storage
        self.evidence_root = evidence_root
        self.audit = audit

    def run(self, *, now: datetime, apply: bool = False) -> RetentionExecutionResult:
        generated_at = _utc_text(now)
        execution_id = now.astimezone(UTC).strftime("%Y%m%d")
        plan = self.storage.plan_retention(now=now)
        candidates = [
            {
                "owner_id": str(candidate.key.owner_id),
                "namespace": candidate.key.namespace.value,
                "artifact_type": candidate.key.artifact_type,
                "artifact_id": candidate.key.artifact_id,
                "version": candidate.key.version,
                "size_bytes": candidate.size_bytes,
                "reason_code": candidate.reason_code,
            }
            for candidate in plan.candidates
        ]
        plan_payload: dict[str, object] = {
            "schema_version": RETENTION_PLAN_SCHEMA,
            "execution_id": execution_id,
            "generated_at": generated_at,
            "cutoff": _utc_text(plan.cutoff),
            "dry_run": not apply,
            "candidates": candidates,
            "protected_count": plan.protected_count,
            "reclaimable_bytes": plan.reclaimable_bytes,
            "immutable_evidence_excluded": True,
        }
        mode = "apply" if apply else "dry-run"
        plan_path = self.evidence_root / f"{execution_id}.artifacts.{mode}.plan.json"
        if not plan_path.exists():
            _write_atomic(plan_path, _canonical_bytes(plan_payload))
        if not apply:
            return RetentionExecutionResult(
                execution_id=execution_id,
                dry_run=True,
                candidate_count=len(candidates),
                deleted_count=0,
                reclaimed_bytes=0,
                protected_count=plan.protected_count,
                plan_path=plan_path,
                result_path=None,
            )
        result_path = self.evidence_root / f"{execution_id}.artifacts.result.json"
        if result_path.exists():
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            return RetentionExecutionResult(
                execution_id=execution_id,
                dry_run=False,
                candidate_count=int(payload["candidate_count"]),
                deleted_count=int(payload["deleted_count"]),
                reclaimed_bytes=int(payload["reclaimed_bytes"]),
                protected_count=int(payload["protected_count"]),
                plan_path=plan_path,
                result_path=result_path,
            )
        deleted = 0
        reclaimed = 0
        for candidate in plan.candidates:
            self.audit.append(
                {
                    "schema_version": "nexora-operations-audit-v1",
                    "event_type": "artifact.retention.executed",
                    "occurred_at": generated_at,
                    "execution_id": execution_id,
                    "owner_id": str(candidate.key.owner_id),
                    "artifact_id": candidate.key.artifact_id,
                    "version": candidate.key.version,
                    "reason_code": candidate.reason_code,
                }
            )
            removed = self.storage.delete_expired_unpinned_export(candidate.key, cutoff=plan.cutoff)
            if removed:
                deleted += 1
                reclaimed += removed
        result_payload = {
            "schema_version": RETENTION_RESULT_SCHEMA,
            "execution_id": execution_id,
            "completed_at": generated_at,
            "candidate_count": len(candidates),
            "deleted_count": deleted,
            "reclaimed_bytes": reclaimed,
            "protected_count": plan.protected_count,
            "partial_failure_retriable": True,
            "immutable_evidence_deleted": False,
        }
        _write_atomic(result_path, _canonical_bytes(result_payload))
        return RetentionExecutionResult(
            execution_id=execution_id,
            dry_run=False,
            candidate_count=len(candidates),
            deleted_count=deleted,
            reclaimed_bytes=reclaimed,
            protected_count=plan.protected_count,
            plan_path=plan_path,
            result_path=result_path,
        )


@dataclass(frozen=True, slots=True)
class BackupRetentionResult:
    execution_id: str
    dry_run: bool
    candidate_count: int
    deleted_count: int
    reclaimed_bytes: int
    protected_count: int
    plan_path: Path
    result_path: Path | None


def _backup_inventory(root: Path) -> dict[str, EncryptedBackupManifest]:
    _require_safe_directory(root, "backup root")
    manifests: dict[str, EncryptedBackupManifest] = {}
    encrypted_ids = {path.name.removesuffix(".tar.age") for path in root.glob("*.tar.age") if path.is_file()}
    for path in root.glob("*.manifest.json"):
        if path.is_symlink() or not path.is_file():
            raise PrivateOperationsError("backup manifest inventory contains an unsafe path")
        identifier = path.name.removesuffix(".manifest.json")
        if BACKUP_ID.fullmatch(identifier) is None:
            raise PrivateOperationsError("backup manifest inventory contains an invalid ID")
        manifests[identifier] = verify_backup_copy(root, identifier)
    if set(manifests) != encrypted_ids:
        raise PrivateOperationsError("backup manifest and encrypted-file inventories disagree")
    return manifests


def _month_index(value: datetime) -> int:
    utc = value.astimezone(UTC)
    return utc.year * 12 + utc.month - 1


def plan_backup_retention(
    runtime_backup_root: Path,
    offsite_backup_root: Path,
    *,
    now: datetime,
) -> tuple[list[EncryptedBackupManifest], list[EncryptedBackupManifest]]:
    _utc_text(now)
    runtime = _backup_inventory(runtime_backup_root)
    offsite = _backup_inventory(offsite_backup_root)
    if set(runtime) != set(offsite):
        raise PrivateOperationsError("runtime and offsite backup inventories disagree")
    for identifier, manifest in runtime.items():
        if manifest.canonical_bytes() != offsite[identifier].canonical_bytes():
            raise PrivateOperationsError("runtime and offsite backup manifests disagree")
    ordered = sorted(runtime.values(), key=lambda item: (item.created_at, item.backup_id), reverse=True)
    if not ordered:
        return [], []
    protected: set[str] = {ordered[0].backup_id}
    utc_now = now.astimezone(UTC)
    current_week = utc_now.date().toordinal() - utc_now.weekday()
    current_month = _month_index(utc_now)
    daily: set[object] = set()
    weekly: set[object] = set()
    monthly: set[object] = set()
    for manifest in ordered:
        created = manifest.created_at.astimezone(UTC)
        age_days = (utc_now.date() - created.date()).days
        if age_days < 0:
            protected.add(manifest.backup_id)
            continue
        day_key = created.date()
        if age_days < 14 and day_key not in daily:
            daily.add(day_key)
            protected.add(manifest.backup_id)
        week_key = created.date().toordinal() - created.weekday()
        if current_week - 7 * 7 <= week_key <= current_week and week_key not in weekly:
            weekly.add(week_key)
            protected.add(manifest.backup_id)
        month_key = _month_index(created)
        if current_month - 11 <= month_key <= current_month and month_key not in monthly:
            monthly.add(month_key)
            protected.add(manifest.backup_id)
    kept = [manifest for manifest in ordered if manifest.backup_id in protected]
    candidates = [manifest for manifest in ordered if manifest.backup_id not in protected]
    return candidates, kept


def _remove_backup_pair(
    manifest: EncryptedBackupManifest,
    *,
    runtime_backup_root: Path,
    offsite_backup_root: Path,
) -> int:
    moved: list[tuple[Path, Path]] = []
    tombstones: list[Path] = []
    try:
        for root in (runtime_backup_root, offsite_backup_root):
            tombstone = root / f".retention-{manifest.backup_id}-{uuid4()}"
            tombstone.mkdir(mode=0o700)
            tombstones.append(tombstone)
            for name in (manifest.encrypted_file, f"{manifest.backup_id}.manifest.json"):
                source = root / name
                target = tombstone / name
                os.rename(source, target)
                moved.append((source, target))
            directory = os.open(root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    except OSError as error:
        for source, target in reversed(moved):
            if target.exists() and not source.exists():
                os.rename(target, source)
        for tombstone in reversed(tombstones):
            if tombstone.exists():
                tombstone.rmdir()
        raise PrivateOperationsError("backup retention could not move both verified copies") from error
    for tombstone in tombstones:
        shutil.rmtree(tombstone)
    return manifest.size_bytes * 2


class BackupRetentionExecutor:
    def __init__(
        self,
        *,
        runtime_backup_root: Path,
        offsite_backup_root: Path,
        evidence_root: Path,
        audit: OperationsAuditSink,
    ) -> None:
        _require_safe_directory(runtime_backup_root, "runtime backup root")
        _require_safe_directory(offsite_backup_root, "offsite backup root")
        if runtime_backup_root.resolve() == offsite_backup_root.resolve():
            raise PrivateOperationsError("offsite backup root must differ from the runtime backup root")
        _require_safe_directory(evidence_root, "retention evidence root")
        self.runtime_backup_root = runtime_backup_root
        self.offsite_backup_root = offsite_backup_root
        self.evidence_root = evidence_root
        self.audit = audit

    def run(self, *, now: datetime, apply: bool = False) -> BackupRetentionResult:
        generated_at = _utc_text(now)
        execution_id = now.astimezone(UTC).strftime("%Y%m%d")
        candidates, protected = plan_backup_retention(
            self.runtime_backup_root,
            self.offsite_backup_root,
            now=now,
        )
        mode = "apply" if apply else "dry-run"
        plan_path = self.evidence_root / f"{execution_id}.backups.{mode}.plan.json"
        plan_payload: dict[str, object] = {
            "schema_version": BACKUP_RETENTION_PLAN_SCHEMA,
            "execution_id": execution_id,
            "generated_at": generated_at,
            "dry_run": not apply,
            "retention_tiers": {"daily": 14, "weekly": 8, "monthly": 12},
            "candidate_backup_ids": [item.backup_id for item in candidates],
            "protected_backup_ids": [item.backup_id for item in protected],
            "runtime_copy_counts_as_offsite": False,
        }
        if not plan_path.exists():
            _write_atomic(plan_path, _canonical_bytes(plan_payload))
        if not apply:
            return BackupRetentionResult(
                execution_id=execution_id,
                dry_run=True,
                candidate_count=len(candidates),
                deleted_count=0,
                reclaimed_bytes=0,
                protected_count=len(protected),
                plan_path=plan_path,
                result_path=None,
            )
        result_path = self.evidence_root / f"{execution_id}.backups.result.json"
        if result_path.exists():
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            return BackupRetentionResult(
                execution_id=execution_id,
                dry_run=False,
                candidate_count=int(payload["candidate_count"]),
                deleted_count=int(payload["deleted_count"]),
                reclaimed_bytes=int(payload["reclaimed_bytes"]),
                protected_count=int(payload["protected_count"]),
                plan_path=plan_path,
                result_path=result_path,
            )
        deleted = 0
        reclaimed = 0
        for candidate in candidates:
            self.audit.append(
                {
                    "schema_version": "nexora-operations-audit-v1",
                    "event_type": "backup.retention.executed",
                    "occurred_at": generated_at,
                    "execution_id": execution_id,
                    "backup_id": candidate.backup_id,
                    "reason_code": "BACKUP_OUTSIDE_RETENTION_TIERS",
                }
            )
            reclaimed += _remove_backup_pair(
                candidate,
                runtime_backup_root=self.runtime_backup_root,
                offsite_backup_root=self.offsite_backup_root,
            )
            deleted += 1
        result_payload = {
            "schema_version": BACKUP_RETENTION_RESULT_SCHEMA,
            "execution_id": execution_id,
            "completed_at": generated_at,
            "candidate_count": len(candidates),
            "deleted_count": deleted,
            "reclaimed_bytes": reclaimed,
            "protected_count": len(protected),
            "both_copies_deleted": True,
            "partial_failure_retriable": True,
        }
        _write_atomic(result_path, _canonical_bytes(result_payload))
        return BackupRetentionResult(
            execution_id=execution_id,
            dry_run=False,
            candidate_count=len(candidates),
            deleted_count=deleted,
            reclaimed_bytes=reclaimed,
            protected_count=len(protected),
            plan_path=plan_path,
            result_path=result_path,
        )


def backup_id(now: datetime, entropy: str) -> str:
    _utc_text(now)
    if re.fullmatch(r"[0-9a-f]{8}", entropy) is None:
        raise PrivateOperationsError("backup entropy is invalid")
    return f"{now.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}-{entropy}"


def capacity_report(storage: ArtifactStorage, *, database_bytes: int) -> dict[str, Any]:
    if database_bytes < 0:
        raise PrivateOperationsError("database capacity cannot be negative")
    usage_method = getattr(storage, "usage", None)
    if not callable(usage_method):
        raise PrivateOperationsError("artifact storage does not expose capacity")
    usage = usage_method()
    return {
        "schema_version": "nexora-private-capacity-report-v1",
        "database_bytes": database_bytes,
        "database_soft_limit_bytes": 20 * 1024**3,
        "artifact_allocated_bytes": usage.allocated_bytes,
        "artifact_soft_limit_bytes": usage.soft_limit_bytes,
        "artifact_hard_limit_bytes": usage.hard_limit_bytes,
        "filesystem_free_percent": round(usage.free_percent, 3),
        "artifact_status": usage.status,
        "degraded": (
            database_bytes >= 20 * 1024**3
            or usage.status in {"critical", "write_protect_noncritical"}
            or usage.free_percent < 20
        ),
        "immutable_evidence_dropped": False,
    }
