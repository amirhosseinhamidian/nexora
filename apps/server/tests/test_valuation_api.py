from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from nexora.api import CSRF_HEADER, create_app
from nexora.composition import compose_application
from nexora.config import load_settings
from nexora.identity import AuthenticatedSession
from nexora.security_config import SecuritySettings
from nexora.valuation import (
    PriceObservationView,
    ValuationEvidenceKind,
    ValuationEvidenceState,
    ValuationSourceKind,
    ValuationStatusView,
)
from pydantic import SecretStr

ORIGIN = "https://nexora.private"
OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
SESSION_ID = UUID("549b8f36-d335-43c5-8227-7fd40ea74268")
PORTFOLIO_ID = UUID("00000000-0000-0000-0000-000000000101")
USD = UUID("00000000-0000-0000-0000-000000000301")
BTC = UUID("00000000-0000-0000-0000-000000000302")
PRICE_ID = UUID("00000000-0000-0000-0000-000000000701")
OBSERVED = datetime(2026, 11, 1, 8, tzinfo=UTC)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _application(repository: Mock) -> FastAPI:
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
        valuation_evidence_repository=repository,
    )
    return create_app(container=container)


def _price() -> PriceObservationView:
    return PriceObservationView(
        PRICE_ID,
        BTC,
        USD,
        Decimal("68123.4500"),
        OBSERVED,
        OBSERVED + timedelta(minutes=5),
        ValuationSourceKind.PROVIDER,
        "provider-tick-1",
        "a" * 64,
        "price-1",
        "b" * 64,
        OBSERVED,
    )


@pytest.mark.anyio
async def test_price_write_is_owner_scoped_csrf_protected_and_decimal_safe() -> None:
    repository = Mock()
    repository.create_price_observation.return_value = _price()
    application = _application(repository)
    headers = {"origin": ORIGIN, "content-type": "application/json", CSRF_HEADER: "c" * 43}
    payload = {
        "asset_id": str(BTC),
        "quote_asset_id": str(USD),
        "price": "68123.4500",
        "observed_at": OBSERVED.isoformat(),
        "valid_until": (OBSERVED + timedelta(minutes=5)).isoformat(),
        "source_kind": "provider",
        "source_reference": "provider-tick-1",
        "source_payload_sha256": "a" * 64,
        "idempotency_key": "price-1",
    }
    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        denied = await client.post("/v1/valuation/price-observations", json=payload)
        response = await client.post("/v1/valuation/price-observations", headers=headers, json=payload)

    assert denied.status_code == 403
    assert response.status_code == 201
    assert response.json()["price"] == "68123.45"
    assert response.json()["state"] == "fresh"
    repository.create_price_observation.assert_called_once()
    assert repository.create_price_observation.call_args.kwargs["owner_id"] == OWNER_ID


@pytest.mark.anyio
async def test_owner_id_and_unknown_fields_are_rejected() -> None:
    application = _application(Mock())
    headers = {"origin": ORIGIN, "content-type": "application/json", CSRF_HEADER: "c" * 43}
    payload = {
        "asset_id": str(BTC),
        "quote_asset_id": str(USD),
        "price": "1",
        "observed_at": OBSERVED.isoformat(),
        "valid_until": (OBSERVED + timedelta(minutes=5)).isoformat(),
        "source_kind": "provider",
        "source_reference": "provider-tick-1",
        "source_payload_sha256": "a" * 64,
        "idempotency_key": "price-1",
        "owner_id": str(OWNER_ID),
    }
    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        response = await client.post("/v1/valuation/price-observations", headers=headers, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"


@pytest.mark.anyio
async def test_unapproved_source_kind_is_rejected() -> None:
    application = _application(Mock())
    headers = {"origin": ORIGIN, "content-type": "application/json", CSRF_HEADER: "c" * 43}
    payload = {
        "asset_id": str(BTC),
        "quote_asset_id": str(USD),
        "price": "1",
        "observed_at": OBSERVED.isoformat(),
        "valid_until": (OBSERVED + timedelta(minutes=5)).isoformat(),
        "source_kind": "trd_bot",
        "source_reference": "unapproved-source",
        "source_payload_sha256": "a" * 64,
        "idempotency_key": "price-unapproved-source",
    }
    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        response = await client.post("/v1/valuation/price-observations", headers=headers, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"


@pytest.mark.anyio
async def test_portfolio_status_exposes_fresh_stale_and_missing_lineage() -> None:
    repository = Mock()
    repository.portfolio_status.return_value = (
        USD,
        (
            ValuationStatusView(
                BTC,
                USD,
                OBSERVED,
                ValuationEvidenceState.STALE,
                ValuationEvidenceKind.PRICE_OBSERVATION,
                Decimal("68000"),
                PRICE_ID,
                OBSERVED - timedelta(hours=1),
                OBSERVED - timedelta(minutes=30),
                "provider-tick-old",
            ),
            ValuationStatusView(
                UUID("00000000-0000-0000-0000-000000000303"),
                USD,
                OBSERVED,
                ValuationEvidenceState.MISSING,
                ValuationEvidenceKind.NONE,
                None,
                None,
                None,
                None,
                None,
            ),
        ),
    )
    application = _application(repository)
    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        response = await client.get(
            f"/v1/portfolios/{PORTFOLIO_ID}/valuation-status",
            params={"as_of": OBSERVED.isoformat()},
        )
    assert response.status_code == 200
    assert [item["state"] for item in response.json()["items"]] == ["stale", "missing"]
    assert response.json()["items"][0]["evidence_id"] == str(PRICE_ID)
    assert response.json()["items"][1]["unit_value"] is None
