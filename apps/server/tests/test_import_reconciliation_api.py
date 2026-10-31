from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from nexora.api import CSRF_HEADER, create_app
from nexora.composition import compose_application
from nexora.config import load_settings
from nexora.identity import AuthenticatedSession
from nexora.import_reconciliation import ImportBatchStatus, ImportBatchView, ImportFormat
from nexora.security_config import SecuritySettings
from pydantic import SecretStr

OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
BATCH_ID = UUID("8db8ca4b-cd39-48e4-9834-c5abe9a0a0bd")
SESSION_ID = UUID("549b8f36-d335-43c5-8227-7fd40ea74268")
ORIGIN = "https://nexora.private"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_import_api_derives_owner_and_publication_requires_recent_reauthentication() -> None:
    identity_repository = Mock()
    identity_repository.authenticate_session.return_value = AuthenticatedSession(
        session_id=SESSION_ID,
        owner_id=OWNER_ID,
        rotation_required=False,
        recently_reauthenticated=True,
    )
    now = datetime.now(UTC)
    batch = ImportBatchView(
        import_batch_id=BATCH_ID,
        source_format=ImportFormat.NEXORA_JSON,
        content_sha256="a" * 64,
        status=ImportBatchStatus.PUBLISHED,
        row_count=1,
        ready_count=1,
        duplicate_count=0,
        quarantined_count=0,
        review_reason="Owner reviewed deterministic evidence",
        created_at=now,
        reviewed_at=now,
        published_at=now,
        rows=(),
    )
    repository = Mock()
    repository.publish_batch.return_value = batch
    security = SecuritySettings(
        canonical_origin=ORIGIN,
        rp_id="nexora.private",
        auth_pepper=SecretStr("p" * 43),
        canonical_origin_file=Path("/run/secrets/nexora_origin"),
        auth_pepper_file=Path("/run/secrets/nexora_pepper"),
    )
    container = replace(
        compose_application(load_settings({})),
        identity_repository=identity_repository,
        owner_identity_service=Mock(),
        import_reconciliation_repository=repository,
        security=security,
    )
    application = create_app(container=container)
    headers = {
        "origin": ORIGIN,
        "content-type": "application/json",
        CSRF_HEADER: "c" * 43,
    }
    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        response = await client.post(
            f"/v1/imports/{BATCH_ID}/publication",
            headers=headers,
            json={},
        )

    assert response.status_code == 200
    assert response.json()["schema_version"] == "nexora-import-batch-v1"
    assert repository.publish_batch.call_args.kwargs["owner_id"] == OWNER_ID
    identity_repository.require_recent_reauthentication.assert_called_once_with(session_id=SESSION_ID)
