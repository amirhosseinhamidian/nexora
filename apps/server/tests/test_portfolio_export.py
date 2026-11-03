from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from nexora.adapters.postgresql.models import AccountRecord
from nexora.adapters.postgresql.portfolio_export import _record
from nexora.artifact_storage import ArtifactStorageSettings, LocalFilesystemArtifactStorage
from nexora.portfolio_export import (
    JsonRecord,
    PortfolioExportFormat,
    PortfolioExportProfile,
    PortfolioExportService,
    PortfolioExportSnapshot,
    PortfolioExportValidationError,
    build_portfolio_export,
)

OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
CAPTURED_AT = datetime(2026, 11, 3, 1, 30, tzinfo=UTC)


def _snapshot(*, reverse: bool = False) -> PortfolioExportSnapshot:
    datasets: dict[str, tuple[JsonRecord, ...]] = {
        "transactions": (
            {
                "transaction_id": "00000000-0000-0000-0000-000000000401",
                "quantity": "1.25",
                "recorded_at": "2026-11-03T01:00:00Z",
            },
        ),
        "assets": (
            {
                "asset_id": "00000000-0000-0000-0000-000000000301",
                "symbol": "BTC",
                "precision": 8,
            },
        ),
    }
    if reverse:
        datasets = dict(reversed(tuple(datasets.items())))
    return PortfolioExportSnapshot(
        captured_at=CAPTURED_AT,
        profile=PortfolioExportProfile.PRIVATE_COMPLETE,
        owner_scope_checksum="a" * 64,
        datasets=datasets,
        lineage={"journal_transaction_count": 1, "immutable_evidence_count": 0},
        uncertainty={"portfolio_analytics_states": {"complete": 1, "stale": 0, "missing": 0}},
        excluded_fields=(),
    )


def test_bundle_is_deterministic_complete_and_checksum_verified() -> None:
    formats = (PortfolioExportFormat.PARQUET, PortfolioExportFormat.JSON, PortfolioExportFormat.CSV)
    first = build_portfolio_export(_snapshot(), formats=formats)
    second = build_portfolio_export(_snapshot(reverse=True), formats=tuple(reversed(formats)))

    assert first.content == second.content
    assert first.export_id == second.export_id
    assert first.sha256 == hashlib.sha256(first.content).hexdigest()
    assert first.manifest["complete"] is True
    assert first.manifest["public_download"] is False
    assert first.manifest["record_count"] == 2
    assert first.manifest["content_formats"] == ["json", "csv", "parquet"]

    with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
        assert archive.namelist() == ["manifest.json", "portfolio.csv", "portfolio.json", "portfolio.parquet"]
        manifest = json.loads(archive.read("manifest.json"))
        for descriptor in manifest["files"]:
            content = archive.read(descriptor["path"])
            assert descriptor["size_bytes"] == len(content)
            assert descriptor["sha256"] == hashlib.sha256(content).hexdigest()


def test_csv_and_parquet_are_analysis_ready_and_lossless() -> None:
    bundle = build_portfolio_export(
        _snapshot(),
        formats=(PortfolioExportFormat.CSV, PortfolioExportFormat.PARQUET),
    )
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        csv_rows = list(csv.DictReader(io.StringIO(archive.read("portfolio.csv").decode())))
        parquet = pq.read_table(io.BytesIO(archive.read("portfolio.parquet"))).to_pylist()

    assert len(csv_rows) == len(parquet) == 2
    assert [row["dataset"] for row in parquet] == ["assets", "transactions"]
    assert json.loads(parquet[1]["record_json"])["quantity"] == "1.25"
    assert parquet[1]["record_sha256"] == csv_rows[1]["record_sha256"]


def test_binary_float_and_duplicate_or_empty_formats_fail_closed() -> None:
    snapshot = _snapshot()
    changed = PortfolioExportSnapshot(
        captured_at=snapshot.captured_at,
        profile=snapshot.profile,
        owner_scope_checksum=snapshot.owner_scope_checksum,
        datasets={"assets": ({"price": 1.25},)},  # type: ignore[dict-item]
        lineage=snapshot.lineage,
        uncertainty=snapshot.uncertainty,
        excluded_fields=(),
    )
    with pytest.raises(PortfolioExportValidationError, match="floating-point"):
        build_portfolio_export(changed, formats=(PortfolioExportFormat.JSON,))
    with pytest.raises(PortfolioExportValidationError, match="at least one"):
        build_portfolio_export(snapshot, formats=())
    with pytest.raises(PortfolioExportValidationError, match="duplicate"):
        build_portfolio_export(
            snapshot,
            formats=(PortfolioExportFormat.JSON, PortfolioExportFormat.JSON),
        )


def test_ai_safe_record_excludes_owner_and_external_account_reference() -> None:
    account = AccountRecord(
        account_id=UUID("00000000-0000-0000-0000-000000000201"),
        owner_id=OWNER_ID,
        portfolio_id=UUID("00000000-0000-0000-0000-000000000101"),
        account_key="broker",
        name="Broker",
        kind="brokerage_manual",
        institution_name="Institution",
        external_reference="sensitive-reference",
        status="active",
        row_version=1,
        created_at=CAPTURED_AT,
        updated_at=CAPTURED_AT,
        closed_at=None,
    )

    complete = _record("accounts", account, PortfolioExportProfile.PRIVATE_COMPLETE)
    ai_safe = _record("accounts", account, PortfolioExportProfile.AI_SAFE)

    assert complete["external_reference"] == "sensitive-reference"
    assert "external_reference" not in ai_safe
    assert "owner_id" not in complete
    assert ai_safe["institution_name"] == "Institution"


def test_service_publishes_owner_scoped_immutable_artifact_idempotently(tmp_path: Path) -> None:
    class Source:
        def snapshot(
            self,
            *,
            owner_id: UUID,
            profile: PortfolioExportProfile,
            captured_at: datetime,
        ) -> PortfolioExportSnapshot:
            assert owner_id == OWNER_ID
            assert profile is PortfolioExportProfile.AI_SAFE
            base = _snapshot()
            return PortfolioExportSnapshot(
                captured_at=captured_at,
                profile=profile,
                owner_scope_checksum=base.owner_scope_checksum,
                datasets=base.datasets,
                lineage=base.lineage,
                uncertainty=base.uncertainty,
                excluded_fields=("accounts.external_reference",),
            )

    storage = LocalFilesystemArtifactStorage(
        ArtifactStorageSettings(root=tmp_path / "artifacts"),
        disk_usage=lambda _: (1_000_000, 0, 1_000_000),
    )
    service = PortfolioExportService(Source(), storage, clock=lambda: CAPTURED_AT)
    first = service.create(
        owner_id=OWNER_ID,
        profile=PortfolioExportProfile.AI_SAFE,
        formats=(PortfolioExportFormat.JSON,),
        pinned=True,
    )
    second = service.create(
        owner_id=OWNER_ID,
        profile=PortfolioExportProfile.AI_SAFE,
        formats=(PortfolioExportFormat.JSON,),
        pinned=True,
    )

    assert first == second
    assert first.artifact.key.owner_id == OWNER_ID
    assert first.artifact.key.artifact_type == "portfolio-export"
    assert first.artifact.retention_class.value == "pinned_export"
    assert first.download_path.startswith("/v1/exports/portfolio-export/pex_")
    assert "http" not in first.download_path
