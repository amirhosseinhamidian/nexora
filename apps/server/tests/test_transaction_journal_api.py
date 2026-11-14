from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from nexora.api import CSRF_HEADER, create_app
from nexora.composition import compose_application
from nexora.config import load_settings
from nexora.identity import AuthenticatedSession
from nexora.security_config import SecuritySettings
from nexora.transaction_journal import (
    JournalSourceKind,
    TransactionKind,
    TransactionLegView,
    TransactionView,
)
from pydantic import SecretStr

OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
PORTFOLIO_ID = UUID("d23455ee-e8c6-4bea-89f0-042eb16b77f9")
ACCOUNT_ID = UUID("f2abdf8f-79e1-4c6d-a170-6af41af5b131")
ASSET_ID = UUID("aab87282-d600-4ec3-a33a-bb0bb5f16930")
TRANSACTION_ID = UUID("8db8ca4b-cd39-48e4-9834-c5abe9a0a0bd")
SESSION_ID = UUID("549b8f36-d335-43c5-8227-7fd40ea74268")
ORIGIN = "https://nexora.private"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_transaction_api_derives_owner_and_requires_idempotency_header() -> None:
    identity_repository = Mock()
    identity_repository.authenticate_session.return_value = AuthenticatedSession(
        session_id=SESSION_ID,
        owner_id=OWNER_ID,
        rotation_required=False,
        recently_reauthenticated=True,
    )
    journal = Mock()
    now = datetime.now(UTC)
    journal.post_transaction.return_value = TransactionView(
        transaction_id=TRANSACTION_ID,
        portfolio_id=PORTFOLIO_ID,
        transaction_kind=TransactionKind.OPENING_BALANCE,
        idempotency_key="manual-20261031-0001",
        occurred_at=now,
        recorded_at=now,
        source_kind=JournalSourceKind.MANUAL,
        source_reference="manual-entry-1",
        source_payload_sha256="a" * 64,
        request_sha256="b" * 64,
        memo=None,
        correction_of_transaction_id=None,
        correction_kind=None,
        correction_reason=None,
        legs=(
            TransactionLegView(uuid4(), 1, ACCOUNT_ID, None, ASSET_ID, Decimal("10"), None),
            TransactionLegView(uuid4(), 2, None, "Opening equity", ASSET_ID, Decimal("-10"), None),
        ),
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
        transaction_journal_repository=journal,
        security=security,
    )
    application = create_app(container=container)
    headers = {
        "origin": ORIGIN,
        "content-type": "application/json",
        CSRF_HEADER: "c" * 43,
        "Idempotency-Key": "manual-20261031-0001",
    }
    payload = {
        "portfolio_id": str(PORTFOLIO_ID),
        "transaction_kind": "opening_balance",
        "occurred_at": now.isoformat(),
        "source_kind": "manual",
        "source_reference": "manual-entry-1",
        "source_payload_sha256": "a" * 64,
        "legs": [
            {"account_id": str(ACCOUNT_ID), "asset_id": str(ASSET_ID), "quantity": "10"},
            {"external_counterparty": "Opening equity", "asset_id": str(ASSET_ID), "quantity": "-10"},
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        created = await client.post("/v1/transactions", headers=headers, json=payload)
        missing_key = await client.post(
            "/v1/transactions",
            headers={key: value for key, value in headers.items() if key != "Idempotency-Key"},
            json=payload,
        )

    assert created.status_code == 201
    assert created.json()["schema_version"] == "nexora-transaction-journal-v1"
    assert created.json()["legs"][0]["quantity"] == "10"
    assert journal.post_transaction.call_args.kwargs["owner_id"] == OWNER_ID
    assert missing_key.status_code == 422
