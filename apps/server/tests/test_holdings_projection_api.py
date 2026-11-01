from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from nexora.adapters.postgresql import HoldingsProjectionView
from nexora.api import CSRF_HEADER, create_app
from nexora.composition import compose_application
from nexora.config import load_settings
from nexora.holdings_projection import (
    BasisStatus,
    CostBasisMethod,
    HoldingProjection,
    LotProjection,
    NegativeHoldingRejected,
    ProjectionSnapshot,
)
from nexora.identity import AuthenticatedSession
from nexora.security_config import SecuritySettings
from pydantic import SecretStr

ORIGIN = "https://nexora.private"
OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
SESSION_ID = UUID("549b8f36-d335-43c5-8227-7fd40ea74268")
PORTFOLIO_ID = UUID("00000000-0000-0000-0000-000000000101")
ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000201")
USD = UUID("00000000-0000-0000-0000-000000000301")
BTC = UUID("00000000-0000-0000-0000-000000000302")
TRANSACTION_ID = UUID("00000000-0000-0000-0000-000000000401")
LEG_ID = UUID("00000000-0000-0000-0000-000000000501")
REBUILD_ID = UUID("00000000-0000-0000-0000-000000000601")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _view() -> HoldingsProjectionView:
    rebuilt_at = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    return HoldingsProjectionView(
        holdings_rebuild_id=REBUILD_ID,
        owner_id=OWNER_ID,
        rebuilt_at=rebuilt_at,
        snapshot=ProjectionSnapshot(
            portfolio_id=PORTFOLIO_ID,
            cost_basis_method=CostBasisMethod.FIFO,
            projection_version="nexora-holdings-projection-v1",
            journal_sha256="a" * 64,
            journal_transaction_count=1,
            last_transaction_id=TRANSACTION_ID,
            holdings=(
                HoldingProjection(
                    ACCOUNT_ID,
                    BTC,
                    Decimal("2"),
                    USD,
                    Decimal("40"),
                    Decimal("20"),
                    BasisStatus.KNOWN,
                ),
            ),
            lots=(
                LotProjection(
                    "b" * 64,
                    None,
                    ACCOUNT_ID,
                    BTC,
                    TRANSACTION_ID,
                    LEG_ID,
                    rebuilt_at,
                    Decimal("2"),
                    Decimal("2"),
                    USD,
                    Decimal("40"),
                    Decimal("40"),
                    BasisStatus.KNOWN,
                ),
            ),
            consumptions=(),
        ),
    )


def _application(projection: Mock) -> FastAPI:
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
        holdings_projection_repository=projection,
    )
    return create_app(container=container)


@pytest.mark.anyio
async def test_rebuild_and_read_endpoints_are_owner_scoped_and_decimal_safe() -> None:
    projection = Mock()
    projection.rebuild.return_value = _view()
    projection.get.return_value = _view()
    application = _application(projection)
    headers = {"origin": ORIGIN, "content-type": "application/json", CSRF_HEADER: "c" * 43}

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        rebuilt = await client.post(
            f"/v1/portfolios/{PORTFOLIO_ID}/holdings/rebuilds",
            headers=headers,
            json={"cost_basis_method": "fifo"},
        )
        holdings = await client.get(f"/v1/portfolios/{PORTFOLIO_ID}/holdings?cost_basis_method=fifo")
        lots = await client.get(f"/v1/portfolios/{PORTFOLIO_ID}/lots?cost_basis_method=fifo")

    assert rebuilt.status_code == 201
    assert rebuilt.json()["holdings"][0]["quantity"] == "2"
    assert rebuilt.json()["holdings"][0]["total_cost_basis"] == "40"
    assert holdings.status_code == 200 and holdings.json()["items"][0]["basis_status"] == "known"
    assert lots.status_code == 200 and lots.json()["items"][0]["lot_key"] == "b" * 64
    projection.rebuild.assert_called_once_with(
        owner_id=OWNER_ID,
        portfolio_id=PORTFOLIO_ID,
        cost_basis_method=CostBasisMethod.FIFO,
    )


@pytest.mark.anyio
async def test_negative_holding_returns_bounded_422_without_internal_quantities() -> None:
    projection = Mock()
    projection.rebuild.side_effect = NegativeHoldingRejected(
        transaction_id=TRANSACTION_ID,
        transaction_leg_id=LEG_ID,
        account_id=ACCOUNT_ID,
        asset_id=BTC,
        requested_quantity=Decimal("2"),
        available_quantity=Decimal("1"),
    )
    application = _application(projection)
    headers = {"origin": ORIGIN, "content-type": "application/json", CSRF_HEADER: "c" * 43}

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        response = await client.post(
            f"/v1/portfolios/{PORTFOLIO_ID}/holdings/rebuilds",
            headers=headers,
            json={"cost_basis_method": "fifo"},
        )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "NEGATIVE_HOLDING_REJECTED",
        "message": "journal would create a negative holding",
    }
    assert "available_quantity" not in response.text
