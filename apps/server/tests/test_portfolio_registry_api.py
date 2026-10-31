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
from nexora.portfolio_registry import AssetClass, AssetView, RegistryStatus
from nexora.security_config import SecuritySettings
from pydantic import SecretStr

OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
ASSET_ID = UUID("d23455ee-e8c6-4bea-89f0-042eb16b77f9")
SESSION_ID = UUID("549b8f36-d335-43c5-8227-7fd40ea74268")
ORIGIN = "https://nexora.private"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_asset_api_uses_authenticated_owner_and_never_accepts_owner_override() -> None:
    identity_repository = Mock()
    identity_repository.authenticate_session.return_value = AuthenticatedSession(
        session_id=SESSION_ID,
        owner_id=OWNER_ID,
        rotation_required=False,
        recently_reauthenticated=True,
    )
    registry = Mock()
    now = datetime.now(UTC)
    registry.create_asset.return_value = AssetView(
        asset_id=ASSET_ID,
        asset_key="usd",
        symbol="USD",
        name="US Dollar",
        asset_class=AssetClass.FIAT,
        precision=2,
        status=RegistryStatus.ACTIVE,
        row_version=1,
        created_at=now,
        updated_at=now,
        deactivated_at=None,
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
        identity_repository=identity_repository,
        owner_identity_service=Mock(),
        portfolio_registry_repository=registry,
        security=security,
    )
    application = create_app(container=container)
    headers = {"origin": ORIGIN, "content-type": "application/json", CSRF_HEADER: "c" * 43}

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        created = await client.post(
            "/v1/assets",
            headers=headers,
            json={
                "asset_key": "usd",
                "symbol": "USD",
                "name": "US Dollar",
                "asset_class": "fiat",
                "precision": 2,
            },
        )
        rejected = await client.post(
            "/v1/assets",
            headers=headers,
            json={
                "asset_key": "btc",
                "symbol": "BTC",
                "name": "Bitcoin",
                "asset_class": "crypto",
                "precision": 8,
                "owner_id": str(UUID(int=2)),
            },
        )

    assert created.status_code == 201
    assert created.json()["schema_version"] == "nexora-asset-registry-v1"
    registry.create_asset.assert_called_once_with(
        owner_id=OWNER_ID,
        asset_key="usd",
        symbol="USD",
        name="US Dollar",
        asset_class=AssetClass.FIAT,
        precision=2,
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
