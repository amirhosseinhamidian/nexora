from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from nexora.api import create_app
from nexora.artifact_storage import (
    ArtifactKey,
    ArtifactManifest,
    ArtifactNamespace,
    ArtifactStorageError,
    RetentionClass,
)
from nexora.composition import compose_application
from nexora.config import load_settings
from nexora.identity import AuthenticatedSession
from nexora.paper_shadow_projection import rebuild_paper_shadow_projection
from nexora.portfolio_export import JsonRecord, PublishedPortfolioExport
from nexora.security_config import SecuritySettings
from pydantic import SecretStr

ORIGIN = "https://nexora.private"
OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
SESSION_ID = UUID("549b8f36-d335-43c5-8227-7fd40ea74268")
CAPTURED_AT = datetime(2026, 11, 3, 1, 30, tzinfo=UTC)
EXPORT_ID = "pex_0123456789abcdef01234567"
VERSION = "v1-0123456789abcdef"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _published() -> PublishedPortfolioExport:
    manifest: JsonRecord = {
        "schema_version": "nexora-portfolio-export-manifest-v1",
        "export_id": EXPORT_ID,
        "profile": "ai_safe",
        "delivery_format": "zip_bundle",
        "content_formats": ["json", "parquet"],
        "generated_at": "2026-11-03T01:30:00Z",
        "owner_scope_checksum": "a" * 64,
        "complete": True,
        "record_count": 1,
        "dataset_counts": {"assets": 1},
        "snapshot_sha256": "b" * 64,
        "lineage": {"immutable_evidence_count": 1},
        "uncertainty": {"open_reconciliation_case_count": 0},
        "excluded_fields": ["accounts.external_reference"],
        "files": [
            {
                "path": "portfolio.json",
                "format": "json",
                "media_type": "application/json",
                "size_bytes": 42,
                "sha256": "c" * 64,
            },
            {
                "path": "portfolio.parquet",
                "format": "parquet",
                "media_type": "application/vnd.apache.parquet",
                "size_bytes": 84,
                "sha256": "d" * 64,
            },
        ],
        "public_download": False,
    }
    artifact = ArtifactManifest(
        key=ArtifactKey(OWNER_ID, ArtifactNamespace.EXPORT, "portfolio-export", EXPORT_ID, VERSION),
        file_name=f"{EXPORT_ID}.zip",
        media_type="application/zip",
        content_schema_version="nexora-portfolio-export-bundle-v1",
        size_bytes=126,
        sha256="e" * 64,
        retention_class=RetentionClass.PINNED_EXPORT,
        published_at=CAPTURED_AT,
    )
    return PublishedPortfolioExport(
        manifest=manifest,
        artifact=artifact,
        download_path=f"/v1/exports/portfolio-export/{EXPORT_ID}/versions/{VERSION}/download",
    )


def _application(export_service: Mock, projection_repository: Mock) -> tuple[FastAPI, Mock]:
    identity = Mock()
    identity.authenticate_session.return_value = AuthenticatedSession(
        session_id=SESSION_ID,
        owner_id=OWNER_ID,
        rotation_required=False,
        recently_reauthenticated=True,
    )
    security = SecuritySettings(
        canonical_origin=ORIGIN,
        rp_id="nexora.private",
        auth_pepper=SecretStr("p" * 43),
        canonical_origin_file=Path("/run/secrets/nexora_origin"),
        auth_pepper_file=Path("/run/secrets/nexora_pepper"),
    )
    container = replace(
        compose_application(load_settings({})),
        identity_repository=identity,
        owner_identity_service=Mock(),
        security=security,
        portfolio_export_service=export_service,
        paper_shadow_projection_repository=projection_repository,
    )
    return create_app(container=container), identity


@pytest.mark.anyio
async def test_create_export_is_owner_scoped_csrf_protected_and_private() -> None:
    export_service = Mock()
    export_service.create.return_value = _published()
    projection_repository = Mock()
    application, identity = _application(export_service, projection_repository)
    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        response = await client.post(
            "/v1/portfolio-exports",
            headers={"origin": ORIGIN, "X-CSRF-Token": "c" * 43},
            json={"profile": "ai_safe", "formats": ["parquet", "json"], "pinned": True},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["manifest"]["complete"] is True
    assert body["manifest"]["public_download"] is False
    assert body["download_path"].startswith("/v1/exports/portfolio-export/")
    assert "owner_id" not in body
    assert export_service.create.call_args.kwargs["owner_id"] == OWNER_ID
    assert export_service.create.call_args.kwargs["pinned"] is True
    assert identity.authenticate_session.call_count == 2


@pytest.mark.anyio
async def test_create_export_rejects_missing_csrf_duplicates_and_unknown_fields() -> None:
    export_service = Mock()
    export_service.create.return_value = _published()
    application, _ = _application(export_service, Mock())
    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        missing_csrf = await client.post(
            "/v1/portfolio-exports",
            headers={"origin": ORIGIN},
            json={"profile": "ai_safe", "formats": ["json"]},
        )
        duplicate = await client.post(
            "/v1/portfolio-exports",
            headers={"origin": ORIGIN, "X-CSRF-Token": "c" * 43},
            json={"profile": "ai_safe", "formats": ["json", "json"]},
        )
        unknown = await client.post(
            "/v1/portfolio-exports",
            headers={"origin": ORIGIN, "X-CSRF-Token": "c" * 43},
            json={"profile": "ai_safe", "formats": ["json"], "public": True},
        )

    assert missing_csrf.status_code == 403
    assert duplicate.status_code == 422
    assert unknown.status_code == 422
    export_service.create.assert_not_called()


@pytest.mark.anyio
async def test_paper_shadow_projection_read_is_owner_scoped() -> None:
    projection_repository = Mock()
    projection_repository.rebuild.return_value = rebuild_paper_shadow_projection(())
    application, _ = _application(Mock(), projection_repository)
    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        response = await client.get("/v1/trd-bot/paper-shadow-projection")

    assert response.status_code == 200
    assert response.json()["complete"] is False
    assert response.json()["issues"][0]["code"] == "NO_EVIDENCE"
    assert projection_repository.rebuild.call_args.kwargs == {"owner_id": OWNER_ID}


@pytest.mark.anyio
async def test_export_storage_failure_is_fail_closed() -> None:
    export_service = Mock()
    export_service.create.side_effect = ArtifactStorageError("private storage unavailable")
    application, _ = _application(export_service, Mock())
    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        response = await client.post(
            "/v1/portfolio-exports",
            headers={"origin": ORIGIN, "X-CSRF-Token": "c" * 43},
            json={"profile": "private_complete", "formats": ["json"]},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ARTIFACT_STORAGE_UNAVAILABLE"
