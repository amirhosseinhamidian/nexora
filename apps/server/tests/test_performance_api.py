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
from nexora.api import create_app
from nexora.composition import compose_application
from nexora.config import load_settings
from nexora.holdings_projection import BasisStatus, CostBasisMethod
from nexora.identity import AuthenticatedSession
from nexora.performance import (
    PERFORMANCE_POLICY_VERSION,
    AnalyticsState,
    PerformancePoint,
    PerformancePointState,
    PerformanceSeries,
    PortfolioAnalyticsSnapshot,
    PositionValue,
    ResolvedValuation,
)
from nexora.security_config import SecuritySettings
from nexora.valuation import ValuationEvidenceKind, ValuationEvidenceState
from pydantic import SecretStr

ORIGIN = "https://nexora.private"
OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
SESSION_ID = UUID("549b8f36-d335-43c5-8227-7fd40ea74268")
PORTFOLIO_ID = UUID("00000000-0000-0000-0000-000000000101")
ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000201")
USD = UUID("00000000-0000-0000-0000-000000000301")
BTC = UUID("00000000-0000-0000-0000-000000000302")
AS_OF = datetime(2026, 11, 1, 12, tzinfo=UTC)


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
        portfolio_performance_repository=repository,
    )
    return create_app(container=container)


def _snapshot() -> PortfolioAnalyticsSnapshot:
    valuation = ResolvedValuation(
        BTC,
        USD,
        AS_OF,
        ValuationEvidenceState.FRESH,
        ValuationEvidenceKind.PRICE_OBSERVATION,
        Decimal("20"),
        (UUID("00000000-0000-0000-0000-000000000701"),),
        AS_OF - timedelta(minutes=1),
        AS_OF + timedelta(minutes=4),
        ("provider-tick-1",),
    )
    position = PositionValue(
        ACCOUNT_ID,
        BTC,
        Decimal("3"),
        valuation,
        Decimal("60"),
        BasisStatus.KNOWN,
        USD,
        Decimal("45"),
        Decimal("45"),
        Decimal("15"),
    )
    return PortfolioAnalyticsSnapshot(
        PORTFOLIO_ID,
        USD,
        AS_OF,
        CostBasisMethod.FIFO,
        PERFORMANCE_POLICY_VERSION,
        "a" * 64,
        4,
        AnalyticsState.COMPLETE,
        Decimal("60"),
        Decimal("60"),
        Decimal("65"),
        Decimal("15"),
        (position,),
        (),
    )


@pytest.mark.anyio
async def test_analytics_is_owner_scoped_and_decimal_safe() -> None:
    repository = Mock()
    repository.snapshot.return_value = _snapshot()
    application = _application(repository)
    url = f"/v1/portfolios/{PORTFOLIO_ID}/analytics?as_of={AS_OF.isoformat().replace('+00:00', 'Z')}"
    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        response = await client.get(url)
    assert response.status_code == 200
    assert response.json()["nav"] == "60"
    assert response.json()["positions"][0]["unrealized_pnl"] == "15"
    assert repository.snapshot.call_args.kwargs["owner_id"] == OWNER_ID
    assert repository.snapshot.call_args.kwargs["cost_basis_method"] is CostBasisMethod.FIFO


@pytest.mark.anyio
async def test_performance_query_is_bounded_and_serialized() -> None:
    repository = Mock()
    repository.performance_series.return_value = PerformanceSeries(
        PORTFOLIO_ID,
        USD,
        CostBasisMethod.FIFO,
        PERFORMANCE_POLICY_VERSION,
        AS_OF,
        AS_OF + timedelta(days=1),
        (
            PerformancePoint(
                AS_OF,
                Decimal("100"),
                Decimal(0),
                None,
                Decimal(0),
                PerformancePointState.AVAILABLE,
                None,
            ),
            PerformancePoint(
                AS_OF + timedelta(days=1),
                Decimal("110"),
                Decimal(0),
                Decimal("0.1"),
                Decimal("0.1"),
                PerformancePointState.AVAILABLE,
                None,
            ),
        ),
    )
    application = _application(repository)
    base = f"/v1/portfolios/{PORTFOLIO_ID}/performance"
    query = (
        f"start_at={AS_OF.isoformat().replace('+00:00', 'Z')}"
        f"&end_at={(AS_OF + timedelta(days=1)).isoformat().replace('+00:00', 'Z')}"
    )
    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        rejected = await client.get(f"{base}?{query}&point_count=33")
        response = await client.get(f"{base}?{query}&point_count=2")
    assert rejected.status_code == 422
    assert response.status_code == 200
    assert response.json()["points"][1]["period_return"] == "0.1"
    assert repository.performance_series.call_args.kwargs["point_count"] == 2
