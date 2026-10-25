from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from nexora.adapters.trd_bot import (
    CONTRACT_VERSION,
    CapabilityNegotiationRequired,
    CursorExpiredError,
    DecisionReviewCommand,
    ExportRequest,
    IncompatibleProviderError,
    ResourceType,
    TrdBotClient,
    TrdBotResponseError,
    TrdBotSchemaError,
    TrdBotSettings,
)
from pydantic import SecretStr

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "contracts/integration/v1/fixtures"
TOKEN = "test-token-" + "x" * 48


def _fixture(name: str) -> dict[str, Any]:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _settings() -> TrdBotSettings:
    return TrdBotSettings(
        base_url="https://trd-bot.private",
        token=SecretStr(TOKEN),
        base_url_file=Path("/private/trd-bot.url"),
        token_file=Path("/private/trd-bot.token"),
    )


def _headers(request: httpx.Request, *, provider_version: str = "0.3.1") -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Correlation-ID": request.headers["X-Correlation-ID"],
        "X-TRD-Bot-Version": provider_version,
        "X-Contract-Version": CONTRACT_VERSION,
    }


def _client(handler: Callable[[httpx.Request], httpx.Response], **kwargs: Any) -> TrdBotClient:
    return TrdBotClient(_settings(), transport=httpx.MockTransport(handler), **kwargs)


def test_compatible_capabilities_are_negotiated_with_secret_backend_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/capabilities")
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        assert request.headers["Accept"] == "application/json"
        return httpx.Response(200, json=_fixture("capabilities-response.json"), headers=_headers(request))

    with _client(handler) as client:
        capabilities = client.negotiate()

    assert capabilities.provider_version == "0.3.1"


def test_provider_0_3_0_remains_fail_closed() -> None:
    payload = _fixture("capabilities-response.json")
    payload["provider_version"] = "0.3.0"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, headers=_headers(request, provider_version="0.3.0"))

    with _client(handler) as client, pytest.raises(IncompatibleProviderError, match="compatibility range"):
        client.negotiate()


def test_missing_capability_is_rejected() -> None:
    payload = _fixture("capabilities-response.json")
    payload["event_envelopes"] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, headers=_headers(request))

    with _client(handler) as client, pytest.raises(IncompatibleProviderError, match="event envelopes"):
        client.negotiate()


def test_reads_require_negotiation() -> None:
    with (
        _client(lambda _: pytest.fail("transport must not be called")) as client,
        pytest.raises(CapabilityNegotiationRequired),
    ):
        client.list_events()


def test_snapshot_read_uses_bounded_page_and_opaque_cursor() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/capabilities"):
            payload = _fixture("capabilities-response.json")
        else:
            payload = {
                "schema_version": "nexora-source-snapshot-page-v1",
                "items": [{"schema_version": "decision-evaluation-v1", "decision_id": "decision-1"}],
                "next_cursor": "opaque-cursor-2",
                "has_more": True,
            }
        return httpx.Response(200, json=payload, headers=_headers(request))

    with _client(handler) as client:
        client.negotiate()
        page = client.list_snapshots(ResourceType.DECISION_EVALUATION, cursor="opaque-cursor-1", limit=250)

    assert page.next_cursor == "opaque-cursor-2"
    assert dict(requests[1].url.params) == {"cursor": "opaque-cursor-1", "limit": "250"}


def test_event_fixture_is_validated_after_negotiation() -> None:
    event = _fixture("decision-event.json")

    def handler(request: httpx.Request) -> httpx.Response:
        payload = _fixture("capabilities-response.json") if request.url.path.endswith("/capabilities") else event
        return httpx.Response(200, json=payload, headers=_headers(request))

    with _client(handler) as client:
        client.negotiate()
        result = client.get_event(str(event["event_id"]))

    assert result.event_id == event["event_id"]


def test_commands_and_exports_use_the_frozen_routes_and_idempotency_headers() -> None:
    correlation_id = UUID("d7d23916-e3d5-41ee-932e-1f1ae08c1825")
    export_id = "exp_bundle_01JAX72D8C5F3K9M"
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/capabilities"):
            status, payload = 200, _fixture("capabilities-response.json")
        elif request.url.path.endswith("/commands/decision-reviews"):
            assert request.headers["Idempotency-Key"] == "nexora-review-decision-20261022-0001"
            status, payload = 202, _fixture("command-receipt.json")
        elif request.method == "POST":
            assert request.headers["Idempotency-Key"] == "nexora-export-20261022-0001"
            status, payload = (
                202,
                {
                    "schema_version": "nexora-export-status-v1",
                    "export_id": export_id,
                    "status": "accepted",
                    "requested_at": "2026-10-22T12:05:00Z",
                    "completed_at": None,
                },
            )
        elif request.url.path.endswith("/manifest"):
            status, payload = 200, _fixture("export-manifest.json")
        else:
            status, payload = (
                200,
                {
                    "schema_version": "nexora-export-status-v1",
                    "export_id": export_id,
                    "status": "complete",
                    "requested_at": "2026-10-22T12:05:00Z",
                    "completed_at": "2026-10-22T12:10:00Z",
                },
            )
        return httpx.Response(status, json=payload, headers=_headers(request))

    command = DecisionReviewCommand.model_validate(_fixture("decision-review-command.json"))
    export = ExportRequest(
        mode="incremental",
        formats=("jsonl", "parquet"),
        profile="ai_safe",
        scope=(ResourceType.DECISION_EVALUATION, ResourceType.PORTFOLIO_INTELLIGENCE),
        filters={"from": "2026-10-01T00:00:00Z"},
    )
    with _client(handler) as client:
        client.negotiate(correlation_id=correlation_id)
        receipt = client.submit_decision_review(
            command,
            idempotency_key="nexora-review-decision-20261022-0001",
            correlation_id=correlation_id,
        )
        accepted = client.create_export(
            export,
            idempotency_key="nexora-export-20261022-0001",
            correlation_id=correlation_id,
        )
        completed = client.get_export(export_id, correlation_id=correlation_id)
        manifest = client.get_export_manifest(export_id, correlation_id=correlation_id)

    assert receipt.status == "accepted"
    assert accepted.status == "accepted"
    assert completed.status == "complete"
    assert manifest.export_id == export_id
    assert calls == [
        ("GET", "/api/v1/integration/nexora/capabilities"),
        ("POST", "/api/v1/integration/nexora/commands/decision-reviews"),
        ("POST", "/api/v1/integration/nexora/exports"),
        ("GET", f"/api/v1/integration/nexora/exports/{export_id}"),
        ("GET", f"/api/v1/integration/nexora/exports/{export_id}/manifest"),
    ]


def test_safe_get_retries_retryable_status_with_bounded_delay() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        if request.url.path.endswith("/capabilities"):
            return httpx.Response(200, json=_fixture("capabilities-response.json"), headers=_headers(request))
        attempts += 1
        if attempts < 3:
            return httpx.Response(503, json={}, headers={"Retry-After": "0"})
        payload: dict[str, Any] = {
            "schema_version": "trd-integration-event-page-v1",
            "events": [],
            "next_cursor": None,
            "has_more": False,
        }
        return httpx.Response(200, json=payload, headers=_headers(request))

    with _client(handler, sleep=delays.append, jitter=lambda _low, high: high) as client:
        client.negotiate()
        client.list_events()

    assert attempts == 3
    assert delays == [0.0, 0.0]


def test_expired_cursor_requires_full_snapshot_resync() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/capabilities"):
            return httpx.Response(200, json=_fixture("capabilities-response.json"), headers=_headers(request))
        error = copy.deepcopy(_fixture("incompatible-error.json"))
        error["error"] = {
            "code": "CURSOR_EXPIRED",
            "message": "The cursor has expired.",
            "retryable": False,
            "details": {},
        }
        return httpx.Response(410, json=error)

    with _client(handler) as client:
        client.negotiate()
        with pytest.raises(CursorExpiredError) as raised:
            client.list_events(cursor="expired")

    assert raised.value.code == "CURSOR_EXPIRED"


def test_412_invalidates_prior_negotiation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/capabilities"):
            return httpx.Response(200, json=_fixture("capabilities-response.json"), headers=_headers(request))
        return httpx.Response(412, json=_fixture("incompatible-error.json"))

    with _client(handler) as client:
        client.negotiate()
        with pytest.raises(TrdBotResponseError):
            client.list_events()
        with pytest.raises(CapabilityNegotiationRequired):
            client.list_events()


def test_unexpected_success_status_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=_fixture("capabilities-response.json"), headers=_headers(request))

    with _client(handler) as client, pytest.raises(TrdBotSchemaError, match="status is invalid"):
        client.negotiate()


def test_post_requires_a_valid_idempotency_key() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json=_fixture("capabilities-response.json"),
            headers=_headers(request),
        )

    export = ExportRequest(
        mode="full",
        formats=("json",),
        profile="private",
        scope=(ResourceType.DECISION_EVALUATION,),
        filters={},
    )
    with _client(handler) as client:
        client.negotiate()
        with pytest.raises(ValueError, match="idempotency key"):
            client.create_export(export, idempotency_key="short")

    assert calls == 1


def test_provider_version_change_invalidates_negotiation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/capabilities"):
            return httpx.Response(200, json=_fixture("capabilities-response.json"), headers=_headers(request))
        payload: dict[str, Any] = {
            "schema_version": "trd-integration-event-page-v1",
            "events": [],
            "next_cursor": None,
            "has_more": False,
        }
        return httpx.Response(200, json=payload, headers=_headers(request, provider_version="0.3.2"))

    with _client(handler) as client:
        client.negotiate()
        with pytest.raises(IncompatibleProviderError, match="changed after negotiation"):
            client.list_events()
        assert client.negotiated_provider_version is None
