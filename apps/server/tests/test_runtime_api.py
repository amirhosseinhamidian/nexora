from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from nexora.api import CORRELATION_HEADER, CSRF_HEADER, create_app
from nexora.composition import compose_application
from nexora.config import load_settings
from nexora.identity import AuthenticatedSession, IssuedSession, VerifiedCredential
from nexora.security_config import SecuritySettings
from pydantic import SecretStr

CORRELATION_ID = "d7d23916-e3d5-41ee-932e-1f1ae08c1825"
OWNER_ID = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
SESSION_ID = UUID("549b8f36-d335-43c5-8227-7fd40ea74268")
ORIGIN = "https://nexora.private"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _security() -> SecuritySettings:
    return SecuritySettings(
        canonical_origin=ORIGIN,
        rp_id="nexora.private",
        auth_pepper=SecretStr("p" * 43),
        canonical_origin_file=Path("/run/secrets/nexora_origin"),
        auth_pepper_file=Path("/run/secrets/nexora_pepper"),
    )


def _container() -> tuple[object, Mock, Mock]:
    repository = Mock()
    service = Mock()
    base = compose_application(load_settings({}))
    container = replace(
        base,
        identity_repository=repository,
        owner_identity_service=service,
        security=_security(),
    )
    return container, repository, service


@pytest.mark.anyio
async def test_version_and_error_envelope_carry_the_same_correlation_id() -> None:
    application = create_app(load_settings({}))
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        version = await client.get("/version", headers={CORRELATION_HEADER: CORRELATION_ID})
        missing = await client.get("/missing", headers={CORRELATION_HEADER: CORRELATION_ID})

    assert version.status_code == 200
    assert version.headers[CORRELATION_HEADER] == CORRELATION_ID
    assert version.json() == {
        "schema_version": "nexora-runtime-api-v1",
        "service": "nexora-api",
        "version": "0.1.0",
        "commit_sha": "development",
        "configuration_schema": "nexora-runtime-configuration-v1",
        "configuration_checksum": "5d4f9f7b6a1b7e1d8ab7af749136afff0b9e4de419d05f34a47497e68818ea04",
    }
    assert missing.status_code == 404
    assert missing.headers[CORRELATION_HEADER] == CORRELATION_ID
    assert missing.json() == {
        "schema_version": "nexora-error-envelope-v1",
        "correlation_id": CORRELATION_ID,
        "error": {"code": "HTTP_404", "message": "resource is unavailable"},
    }


@pytest.mark.anyio
async def test_invalid_correlation_and_origin_fail_closed_without_reflecting_input() -> None:
    container, _, _ = _container()
    application = create_app(container=container)  # type: ignore[arg-type]
    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        malformed = await client.get("/version", headers={CORRELATION_HEADER: "not-a-uuid"})
        denied = await client.post(
            "/v1/auth/authentication/options",
            headers={"origin": "https://attacker.invalid", "content-type": "application/json"},
            json={},
        )

    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "INVALID_CORRELATION_ID"
    assert "not-a-uuid" not in malformed.text
    assert denied.status_code == 403
    assert denied.json()["error"] == {"code": "ORIGIN_DENIED", "message": "request denied"}


@pytest.mark.anyio
async def test_authentication_session_rotation_and_logout_use_host_cookie_and_csrf() -> None:
    container, repository, service = _container()
    now = datetime.now(UTC)
    issued = IssuedSession(
        session_id=SESSION_ID,
        owner_id=OWNER_ID,
        token="s" * 43,
        csrf_token="c" * 43,
        idle_expires_at=now + timedelta(minutes=30),
        absolute_expires_at=now + timedelta(hours=12),
    )
    authenticated = AuthenticatedSession(
        session_id=SESSION_ID,
        owner_id=OWNER_ID,
        rotation_required=False,
        recently_reauthenticated=True,
    )
    service.begin_authentication.return_value = (
        OWNER_ID,
        "q" * 43,
        (
            VerifiedCredential(
                credential_id="credential-id-1234",
                public_key=b"k" * 64,
                algorithm="ES256",
                sign_count=0,
                transports=("internal",),
            ),
        ),
    )
    service.complete_authentication.return_value = issued
    repository.authenticate_session.return_value = authenticated
    repository.rotate_session.return_value = issued
    application = create_app(container=container)  # type: ignore[arg-type]
    common_headers = {"origin": ORIGIN, "content-type": "application/json"}

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        options = await client.post("/v1/auth/authentication/options", headers=common_headers, json={})
        completed = await client.post(
            "/v1/auth/authentication/complete",
            headers=common_headers,
            json={
                "credential_id": "credential-id-1234",
                "challenge": "q" * 43,
                "response_json": "{}",
            },
        )
        session = await client.get("/v1/auth/session")
        rotated = await client.post(
            "/v1/auth/session/rotate",
            headers={**common_headers, CSRF_HEADER: issued.csrf_token},
            json={},
        )
        logged_out = await client.post(
            "/v1/auth/logout",
            headers={**common_headers, CSRF_HEADER: issued.csrf_token},
            json={},
        )

    assert options.status_code == 200
    assert options.json()["allow_credentials"] == [{"credential_id": "credential-id-1234", "transports": ["internal"]}]
    assert completed.status_code == 200
    set_cookie = completed.headers["set-cookie"]
    assert "__Host-nexora_session=" in set_cookie
    assert "Secure" in set_cookie and "HttpOnly" in set_cookie and "SameSite=strict" in set_cookie
    assert "Domain=" not in set_cookie
    assert completed.json()["csrf_token"] == issued.csrf_token
    assert session.json()["recently_reauthenticated"] is True
    assert rotated.status_code == 200
    assert logged_out.status_code == 200
    repository.revoke_session.assert_called_once_with(token=issued.token)


@pytest.mark.anyio
async def test_authenticated_mutation_requires_csrf_and_logout_all_requires_recent_authentication() -> None:
    container, repository, service = _container()
    session = AuthenticatedSession(
        session_id=SESSION_ID,
        owner_id=OWNER_ID,
        rotation_required=False,
        recently_reauthenticated=True,
    )
    repository.authenticate_session.return_value = session
    application = create_app(container=container)  # type: ignore[arg-type]
    headers = {"origin": ORIGIN, "content-type": "application/json"}

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        denied = await client.post("/v1/auth/registration/options", headers=headers, json={})
        accepted = await client.post(
            "/v1/auth/logout-all",
            headers={**headers, CSRF_HEADER: "c" * 43},
            json={},
        )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "CSRF_DENIED"
    assert accepted.status_code == 200
    repository.require_recent_reauthentication.assert_called_once_with(session_id=SESSION_ID)
    repository.revoke_all_sessions.assert_called_once_with(owner_id=OWNER_ID)
    service.begin_registration.assert_not_called()
