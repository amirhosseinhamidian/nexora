from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final, Protocol, cast
from uuid import UUID

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from nexora.artifact_storage import (
    ArtifactKey,
    ArtifactManifest,
    ArtifactNamespace,
    ArtifactPublishRequest,
    ArtifactStorage,
    RetentionClass,
)

PORTFOLIO_EXPORT_SCHEMA: Final = "nexora-portfolio-export-v1"
PORTFOLIO_EXPORT_MANIFEST_SCHEMA: Final = "nexora-portfolio-export-manifest-v1"
PORTFOLIO_EXPORT_BUNDLE_SCHEMA: Final = "nexora-portfolio-export-bundle-v1"
PORTFOLIO_EXPORT_RECORD_SCHEMA: Final = "nexora-portfolio-export-record-v1"
MAX_EXPORT_RECORDS: Final = 100_000
MAX_UNCOMPRESSED_BYTES: Final = 128 * 1024 * 1024
DATASET_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

type JsonScalar = str | int | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonRecord = dict[str, JsonValue]


class PortfolioExportProfile(StrEnum):
    PRIVATE_COMPLETE = "private_complete"
    AI_SAFE = "ai_safe"


class PortfolioExportFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"


class PortfolioExportError(RuntimeError):
    """Base error for deterministic portfolio exports."""


class PortfolioExportValidationError(PortfolioExportError):
    """The requested export or source snapshot violates the frozen contract."""


class PortfolioExportCapacityExceeded(PortfolioExportError):
    """A complete export cannot be built inside the bounded synchronous budget."""


@dataclass(frozen=True, slots=True)
class PortfolioExportSnapshot:
    captured_at: datetime
    profile: PortfolioExportProfile
    owner_scope_checksum: str
    datasets: Mapping[str, tuple[JsonRecord, ...]]
    lineage: JsonRecord
    uncertainty: JsonRecord
    excluded_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioExportBundle:
    export_id: str
    manifest: JsonRecord
    content: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class PublishedPortfolioExport:
    manifest: JsonRecord
    artifact: ArtifactManifest
    download_path: str


class PortfolioExportSource(Protocol):
    def snapshot(
        self,
        *,
        owner_id: UUID,
        profile: PortfolioExportProfile,
        captured_at: datetime,
    ) -> PortfolioExportSnapshot: ...


def canonical_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def canonical_json_sha256(payload: object) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise PortfolioExportValidationError("export timestamp must be timezone-aware UTC")
    return value.isoformat().replace("+00:00", "Z")


def _validate_json_value(value: JsonValue, *, path: str = "record") -> None:
    if isinstance(value, float):
        raise PortfolioExportValidationError(f"binary floating-point is forbidden at {path}")
    if value is None or isinstance(value, (str, int, bool)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise PortfolioExportValidationError(f"JSON object key is not a string at {path}")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise PortfolioExportValidationError(f"unsupported export value at {path}")


def _ordered_formats(formats: Sequence[PortfolioExportFormat]) -> tuple[PortfolioExportFormat, ...]:
    if len(formats) != len(set(formats)):
        raise PortfolioExportValidationError("duplicate export content formats are forbidden")
    requested = set(formats)
    if not requested:
        raise PortfolioExportValidationError("at least one export content format is required")
    return tuple(item for item in PortfolioExportFormat if item in requested)


def _flatten_records(datasets: Mapping[str, tuple[JsonRecord, ...]]) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    for dataset in sorted(datasets):
        for index, record in enumerate(datasets[dataset]):
            record_text = canonical_json_bytes(record).decode().rstrip("\n")
            rows.append(
                {
                    "dataset": dataset,
                    "record_index": index,
                    "record_sha256": hashlib.sha256(record_text.encode()).hexdigest(),
                    "record_json": record_text,
                }
            )
    return rows


def _csv_bytes(rows: Sequence[Mapping[str, str | int]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=("dataset", "record_index", "record_sha256", "record_json"),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _parquet_bytes(rows: Sequence[Mapping[str, str | int]]) -> bytes:
    schema = pa.schema(
        (
            pa.field("dataset", pa.string(), nullable=False),
            pa.field("record_index", pa.int64(), nullable=False),
            pa.field("record_sha256", pa.string(), nullable=False),
            pa.field("record_json", pa.string(), nullable=False),
        )
    )
    table = pa.Table.from_pylist(list(rows), schema=schema)
    stream = io.BytesIO()
    pq.write_table(
        table,
        stream,
        compression="zstd",
        data_page_version="2.0",
        version="2.6",
        use_dictionary=False,
        write_statistics=True,
    )
    return stream.getvalue()


def _zip_entry(name: str) -> zipfile.ZipInfo:
    entry = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.create_system = 3
    entry.external_attr = 0o100440 << 16
    return entry


def build_portfolio_export(
    snapshot: PortfolioExportSnapshot,
    *,
    formats: Sequence[PortfolioExportFormat],
) -> PortfolioExportBundle:
    ordered_formats = _ordered_formats(formats)
    if not re.fullmatch(r"[0-9a-f]{64}", snapshot.owner_scope_checksum):
        raise PortfolioExportValidationError("owner scope checksum is invalid")
    captured_at = _utc_text(snapshot.captured_at)
    datasets: dict[str, tuple[JsonRecord, ...]] = {}
    record_count = 0
    for name in sorted(snapshot.datasets):
        if DATASET_PATTERN.fullmatch(name) is None:
            raise PortfolioExportValidationError("export dataset name is invalid")
        records = snapshot.datasets[name]
        for record in records:
            _validate_json_value(record)
        datasets[name] = records
        record_count += len(records)
        if record_count > MAX_EXPORT_RECORDS:
            raise PortfolioExportCapacityExceeded("complete export exceeds the record budget")

    _validate_json_value(snapshot.lineage)
    _validate_json_value(snapshot.uncertainty)
    snapshot_payload: JsonRecord = {
        "schema_version": PORTFOLIO_EXPORT_SCHEMA,
        "profile": snapshot.profile.value,
        "captured_at": captured_at,
        "owner_scope_checksum": snapshot.owner_scope_checksum,
        "record_count": record_count,
        "datasets": {name: list(records) for name, records in datasets.items()},
        "lineage": snapshot.lineage,
        "uncertainty": snapshot.uncertainty,
        "excluded_fields": list(snapshot.excluded_fields),
    }
    snapshot_bytes = canonical_json_bytes(snapshot_payload)
    if len(snapshot_bytes) > MAX_UNCOMPRESSED_BYTES:
        raise PortfolioExportCapacityExceeded("complete export exceeds the uncompressed byte budget")
    snapshot_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()
    flat_rows = _flatten_records(datasets)
    content_files: dict[str, bytes] = {}
    builders: dict[PortfolioExportFormat, tuple[str, Callable[[], bytes], str]] = {
        PortfolioExportFormat.JSON: ("portfolio.json", lambda: snapshot_bytes, "application/json"),
        PortfolioExportFormat.CSV: ("portfolio.csv", lambda: _csv_bytes(flat_rows), "text/csv"),
        PortfolioExportFormat.PARQUET: (
            "portfolio.parquet",
            lambda: _parquet_bytes(flat_rows),
            "application/vnd.apache.parquet",
        ),
    }
    descriptors: list[JsonRecord] = []
    for output_format in ordered_formats:
        path, builder, media_type = builders[output_format]
        content = builder()
        content_files[path] = content
        descriptors.append(
            {
                "path": path,
                "format": output_format.value,
                "media_type": media_type,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )

    identity_payload = {
        "schema_version": PORTFOLIO_EXPORT_MANIFEST_SCHEMA,
        "profile": snapshot.profile.value,
        "captured_at": captured_at,
        "owner_scope_checksum": snapshot.owner_scope_checksum,
        "snapshot_sha256": snapshot_sha256,
        "files": cast(JsonValue, descriptors),
    }
    export_id = f"pex_{canonical_json_sha256(identity_payload)[:24]}"
    manifest: JsonRecord = {
        "schema_version": PORTFOLIO_EXPORT_MANIFEST_SCHEMA,
        "export_id": export_id,
        "profile": snapshot.profile.value,
        "delivery_format": "zip_bundle",
        "content_formats": [item.value for item in ordered_formats],
        "generated_at": captured_at,
        "owner_scope_checksum": snapshot.owner_scope_checksum,
        "complete": True,
        "record_count": record_count,
        "dataset_counts": {name: len(records) for name, records in datasets.items()},
        "snapshot_sha256": snapshot_sha256,
        "lineage": snapshot.lineage,
        "uncertainty": snapshot.uncertainty,
        "excluded_fields": list(snapshot.excluded_fields),
        "files": cast(JsonValue, descriptors),
        "public_download": False,
    }
    manifest_bytes = canonical_json_bytes(manifest)
    bundle_stream = io.BytesIO()
    with zipfile.ZipFile(bundle_stream, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(_zip_entry("manifest.json"), manifest_bytes)
        for path in sorted(content_files):
            archive.writestr(_zip_entry(path), content_files[path])
    content = bundle_stream.getvalue()
    return PortfolioExportBundle(
        export_id=export_id,
        manifest=manifest,
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
    )


class PortfolioExportService:
    def __init__(
        self,
        source: PortfolioExportSource,
        storage: ArtifactStorage,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._source = source
        self._storage = storage
        self._clock = clock or (lambda: datetime.now(UTC))

    def create(
        self,
        *,
        owner_id: UUID,
        profile: PortfolioExportProfile,
        formats: Sequence[PortfolioExportFormat],
        pinned: bool,
    ) -> PublishedPortfolioExport:
        captured_at = self._clock()
        snapshot = self._source.snapshot(owner_id=owner_id, profile=profile, captured_at=captured_at)
        bundle = build_portfolio_export(snapshot, formats=formats)
        version = f"v1-{bundle.sha256[:16]}"
        request = ArtifactPublishRequest(
            key=ArtifactKey(
                owner_id=owner_id,
                namespace=ArtifactNamespace.EXPORT,
                artifact_type="portfolio-export",
                artifact_id=bundle.export_id,
                version=version,
            ),
            file_name=f"{bundle.export_id}.zip",
            media_type="application/zip",
            content_schema_version=PORTFOLIO_EXPORT_BUNDLE_SCHEMA,
            retention_class=RetentionClass.PINNED_EXPORT if pinned else RetentionClass.UNPINNED_EXPORT,
            published_at=snapshot.captured_at,
        )
        artifact = self._storage.publish_bytes(request, bundle.content)
        return PublishedPortfolioExport(
            manifest=bundle.manifest,
            artifact=artifact,
            download_path=(f"/v1/exports/portfolio-export/{bundle.export_id}/versions/{artifact.key.version}/download"),
        )
