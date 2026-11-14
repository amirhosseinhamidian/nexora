from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from nexora.adapters.postgresql.decision_projection import ActiveDecisionProjection
from nexora.adapters.trd_bot import ResourceType, TrdBotIntegrationMode
from nexora.api import create_app
from nexora.composition import compose_application
from nexora.config import load_settings
from nexora.decision_event_projection import DecisionKind, DecisionProjectionRecord, canonical_json_sha256
from nexora.decision_feed import DecisionFeedConflict, DecisionFeedService, DecisionFeedValidationError
from nexora.identity import AuthenticatedSession
from nexora.security_config import SecuritySettings
from pydantic import SecretStr

ORIGIN = "https://nexora.private"
OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
SESSION_ID = UUID("549b8f36-d335-43c5-8227-7fd40ea74268")
NOW = datetime(2026, 11, 14, 10, tzinfo=UTC)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _record(resource_type: ResourceType, resource_id: str, *, minute: int = 0) -> dict[str, object]:
    payload = {
        "resource_schema_version": f"trd-bot-{resource_type.value.replace('_', '-')}-v1",
        f"{resource_type.value}_id": resource_id,
        "offline_only": True,
        "external_order_submission_allowed": False,
    }
    record = DecisionProjectionRecord(
        resource_type=resource_type,
        resource_id=resource_id,
        decision_kind=(
            DecisionKind.CANDIDATE if resource_type is ResourceType.CANDIDATE else DecisionKind.PORTFOLIO_ASSESSMENT
        ),
        provider_release="0.3.1",
        source_schema_version=str(payload["resource_schema_version"]),
        source_observed_at=NOW.replace(minute=minute),
        source_checksum="sha256:" + "a" * 64,
        aggregate_type=resource_type.value,
        aggregate_id=resource_id,
        aggregate_version=1,
        payload=payload,
        payload_sha256=canonical_json_sha256(payload),
    )
    return record.model_dump(mode="json")


def _snapshot(*records: dict[str, object], generation: int = 3) -> ActiveDecisionProjection:
    return ActiveDecisionProjection(
        generation=generation,
        trigger="cursor_expired",
        provider_version="0.3.1",
        contract_version="nexora-trd-integration-v1",
        projection={f"record:{index}": record for index, record in enumerate(records)},
    )


def _application(repository: Mock, mode: TrdBotIntegrationMode) -> FastAPI:
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
        decision_event_projection_repository=repository,
        trd_bot_integration_mode=mode,
    )
    return create_app(container=container)


def test_feed_is_bounded_sorted_and_cursor_is_generation_bound() -> None:
    repository = Mock()
    repository.active_snapshot.return_value = _snapshot(
        _record(ResourceType.CANDIDATE, "candidate-old", minute=1),
        _record(ResourceType.DECISION_EVALUATION, "decision-new", minute=2),
        _record(ResourceType.CANDIDATE, "candidate-new", minute=3),
    )
    service = DecisionFeedService(repository, TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER)

    first = service.list_feed(OWNER_ID, limit=2, cursor=None)
    second = service.list_feed(OWNER_ID, limit=2, cursor=first.next_cursor)

    assert [item.resource_id for item in first.items] == ["candidate-new", "decision-new"]
    assert [item.resource_id for item in second.items] == ["candidate-old"]
    assert first.provider.state == "ready"
    assert first.items[0].source.source_product == "trd_bot"
    assert first.items[0].source.aggregate_version == 1
    assert second.next_cursor is None

    repository.active_snapshot.return_value = _snapshot(_record(ResourceType.CANDIDATE, "candidate-new"), generation=4)
    with pytest.raises(DecisionFeedConflict, match="snapshot changed"):
        service.list_feed(OWNER_ID, limit=2, cursor=first.next_cursor)
    repository.active_snapshot.return_value = _snapshot(
        _record(ResourceType.CANDIDATE, "candidate-event-update"), generation=3
    )
    with pytest.raises(DecisionFeedConflict, match="snapshot changed"):
        service.list_feed(OWNER_ID, limit=2, cursor=first.next_cursor)
    with pytest.raises(DecisionFeedValidationError, match="cursor is invalid"):
        service.list_feed(OWNER_ID, limit=2, cursor="not-base64!")


def test_invalid_projection_fails_closed_and_disabled_provider_is_explicit() -> None:
    repository = Mock()
    invalid = _record(ResourceType.CANDIDATE, "candidate-1")
    invalid["payload_sha256"] = "f" * 64
    repository.active_snapshot.return_value = _snapshot(invalid)
    service = DecisionFeedService(repository, TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER)

    response = service.list_feed(OWNER_ID, limit=25, cursor=None)

    assert response.items == []
    assert response.provider.state == "degraded"
    assert response.provider.reason_code == "PROJECTION_EVIDENCE_INVALID"

    disabled = DecisionFeedService(repository, TrdBotIntegrationMode.DISABLED_INCOMPATIBLE_PROVIDER)
    disabled_response = disabled.list_feed(OWNER_ID, limit=25, cursor=None)
    assert disabled_response.provider.state == "disabled_incompatible"


@pytest.mark.anyio
async def test_api_is_authenticated_owner_scoped_and_returns_candidate_lineage() -> None:
    repository = Mock()
    repository.active_snapshot.return_value = _snapshot(_record(ResourceType.CANDIDATE, "candidate-1"))
    application = _application(repository, TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER)

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        unauthorized = await client.get("/v1/decisions")
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        feed = await client.get("/v1/decisions?limit=1")
        detail = await client.get("/v1/candidates/candidate-1")

    assert unauthorized.status_code == 401
    assert feed.status_code == 200
    assert feed.json()["items"][0]["resource_id"] == "candidate-1"
    assert detail.status_code == 200
    assert detail.json()["candidate"]["source"]["resource_schema_version"] == "trd-bot-candidate-v1"
    assert repository.active_snapshot.call_args_list[0].args == (OWNER_ID,)


@pytest.mark.anyio
async def test_missing_candidate_and_degraded_projection_are_distinct() -> None:
    repository = Mock()
    repository.active_snapshot.return_value = _snapshot(_record(ResourceType.CANDIDATE, "candidate-1"))
    application = _application(repository, TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER)

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        missing = await client.get("/v1/candidates/missing")
        repository.active_snapshot.return_value = None
        degraded = await client.get("/v1/candidates/candidate-1")

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "DECISION_EVIDENCE_NOT_FOUND"
    assert degraded.status_code == 200
    assert degraded.json()["candidate"] is None
    assert degraded.json()["provider"]["reason_code"] == "ACTIVE_PROJECTION_UNAVAILABLE"
