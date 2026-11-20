from __future__ import annotations

import hashlib
import logging
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from nexora.adapters.postgresql.identity import PostgreSQLIdentityRepository
from nexora.api import CORRELATION_HEADER, CSRF_COOKIE_NAME, CSRF_HEADER, create_app
from nexora.artifact_storage import (
    ArtifactKey,
    ArtifactManifest,
    ArtifactNamespace,
    ArtifactNotFound,
    RetentionClass,
    StoredArtifact,
)
from nexora.composition import ApplicationContainer, compose_application
from nexora.config import DeploymentProfile, RuntimeEnvironment, RuntimeSettings, load_settings
from nexora.identity import (
    SESSION_COOKIE_NAME,
    AuthenticatedSession,
    AuthenticationDenied,
    IssuedSession,
    VerifiedAssertion,
    VerifiedCredential,
    token_digest,
)
from nexora.identity_service import OwnerIdentityService
from nexora.observability import StructuredJsonFormatter
from nexora.overload import InteractiveRequestGate
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


def _container() -> tuple[ApplicationContainer, Mock, Mock]:
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
    application = create_app(container=container)
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
    application = create_app(container=container)
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
    set_cookies = completed.headers.get_list("set-cookie")
    session_cookie = next(cookie for cookie in set_cookies if cookie.startswith("__Host-nexora_session="))
    csrf_cookie = next(cookie for cookie in set_cookies if cookie.startswith("__Host-nexora_csrf="))
    assert "Secure" in session_cookie and "HttpOnly" in session_cookie and "SameSite=strict" in session_cookie
    assert "Secure" in csrf_cookie and "HttpOnly" not in csrf_cookie and "SameSite=strict" in csrf_cookie
    assert all("Path=/" in cookie and "Domain=" not in cookie for cookie in set_cookies)
    assert completed.json()["csrf_token"] == issued.csrf_token
    assert session.json()["recently_reauthenticated"] is True
    assert rotated.status_code == 200
    assert logged_out.status_code == 200
    repository.revoke_session.assert_called_once_with(token=issued.token)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "prior",
    ("absent", "unknown", "idle_expired", "absolute_expired", "revoked", "rotated", "csrf_mismatch", "valid"),
)
async def test_passkey_login_issues_a_fresh_session_independent_of_existing_cookies(
    prior: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    container, repository, _ = _container()
    security = _security()
    verifier = Mock()
    login = OwnerIdentityService(repository, verifier, security)
    container = replace(container, owner_identity_service=login)

    old_token, old_csrf = "o" * 43, "c" * 43
    now = datetime.now(UTC)
    expired_at = now - timedelta(seconds=1)
    new = IssuedSession(
        session_id=UUID("3cf109b5-3ece-4f44-8be7-9abda03617bb"),
        owner_id=OWNER_ID,
        token="n" * 43,
        csrf_token="r" * 43,
        idle_expires_at=now + timedelta(minutes=30),
        absolute_expires_at=now + timedelta(hours=12),
    )
    # Use the actual adapter's validity checks with a mock database result.
    rows = {
        old_token: SimpleNamespace(
            session_id=SESSION_ID,
            owner_id=OWNER_ID,
            csrf_digest=token_digest("m" * 43 if prior == "csrf_mismatch" else old_csrf),
            idle_expires_at=expired_at if prior == "idle_expired" else new.idle_expires_at,
            absolute_expires_at=expired_at if prior == "absolute_expired" else new.absolute_expires_at,
            revoked_at=expired_at if prior == "revoked" else None,
            replaced_at=expired_at if prior == "rotated" else None,
            rotation_grace_expires_at=expired_at if prior == "rotated" else None,
            rotated_at=now,
            reauthenticated_at=now,
        )
    }
    if prior in {"absent", "unknown"}:
        rows.clear()
    database_session = Mock()
    session_factory = Mock()
    session_factory.begin.return_value = nullcontext(database_session)
    adapter = PostgreSQLIdentityRepository(session_factory)

    def authenticate(*, token: str, csrf_token: str | None = None) -> AuthenticatedSession:
        database_session.execute.return_value.scalar_one_or_none.return_value = rows.get(token)
        return adapter.authenticate_session(token=token, csrf_token=csrf_token, now=now)

    def issue(*, owner_id: UUID) -> IssuedSession:
        assert owner_id == OWNER_ID
        rows[new.token] = SimpleNamespace(
            session_id=new.session_id,
            owner_id=new.owner_id,
            csrf_digest=token_digest(new.csrf_token),
            idle_expires_at=new.idle_expires_at,
            absolute_expires_at=new.absolute_expires_at,
            revoked_at=None,
            replaced_at=None,
            rotation_grace_expires_at=None,
            rotated_at=now,
            reauthenticated_at=now,
        )
        return new

    credential = VerifiedCredential(
        credential_id="fixture-credential-id",
        public_key=b"k" * 64,
        algorithm="ES256",
        sign_count=7,
        transports=("internal",),
    )
    challenge = "q" * 43
    assertion = '{"fixture":"synthetic-browser-assertion"}'
    repository.authenticate_session.side_effect = authenticate
    repository.create_session.side_effect = issue
    repository.get_single_owner_id.return_value = OWNER_ID
    repository.issue_challenge.return_value = challenge
    repository.list_active_credentials.return_value = (credential,)
    repository.get_active_credential.return_value = credential
    verifier.verify_authentication.return_value = VerifiedAssertion(credential.credential_id, 8)
    payload = {"credential_id": credential.credential_id, "challenge": challenge, "response_json": assertion}
    headers = {"origin": ORIGIN}

    logger = container.observability.events.logger
    monkeypatch.setattr(logger, "propagate", True)
    caplog.set_level(logging.INFO, logger=logger.name)
    async with AsyncClient(transport=ASGITransport(app=create_app(container=container)), base_url=ORIGIN) as client:
        if prior != "absent":
            client.cookies.set(SESSION_COOKIE_NAME, old_token, domain="nexora.private", path="/")
            client.cookies.set(CSRF_COOKIE_NAME, old_csrf, domain="nexora.private", path="/")
            headers[CSRF_HEADER] = old_csrf
        bad_session = prior not in {"valid", "csrf_mismatch"}
        previous = await client.get("/v1/auth/session")
        assert previous.status_code == (401 if bad_session else 200)
        if bad_session:
            assert previous.json()["error"]["code"] == "AUTHENTICATION_DENIED"
            assert (await client.get("/v1/portfolios")).status_code == 401

        repository.authenticate_session.reset_mock()
        options = await client.post("/v1/auth/authentication/options", headers=headers, json={})
        assert options.status_code == 200
        assert options.json()["challenge"] == challenge
        assert options.headers.get_list("set-cookie") == []
        repository.create_session.assert_not_called()

        completed = await client.post("/v1/auth/authentication/complete", headers=headers, json=payload)
        assert completed.status_code == 200
        assert completed.json()["owner_id"] == str(OWNER_ID)
        assert completed.json()["recently_reauthenticated"] is True
        assert client.cookies.get(SESSION_COOKIE_NAME) == new.token
        assert client.cookies.get(CSRF_COOKIE_NAME) == new.csrf_token
        repository.authenticate_session.assert_not_called()
        repository.issue_challenge.assert_called_once_with(owner_id=OWNER_ID, purpose="authentication")
        verifier.verify_authentication.assert_called_once_with(
            response_json=assertion,
            expected_challenge=challenge,
            expected_origin=ORIGIN,
            expected_rp_id="nexora.private",
            credential=credential,
        )
        repository.consume_challenge.assert_called_once_with(
            owner_id=OWNER_ID, purpose="authentication", challenge=challenge
        )
        repository.create_session.assert_called_once_with(owner_id=OWNER_ID)

        active = await client.get("/v1/auth/session")
        assert active.status_code == 200
        repository.authenticate_session.assert_called_once_with(token=new.token)
        denied = await client.post("/v1/auth/logout", headers={**headers, CSRF_HEADER: old_csrf}, json={})
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "CSRF_DENIED"
        repository.revoke_session.assert_not_called()
        accepted = await client.post("/v1/auth/logout", headers={**headers, CSRF_HEADER: new.csrf_token}, json={})
        assert accepted.status_code == 200
        repository.revoke_session.assert_called_once_with(token=new.token)

    formatter = StructuredJsonFormatter(service="fixture-api")
    logged = "\n".join(formatter.format(event) for event in caplog.records if event.name == logger.name)
    assert "http.request.completed" in logged and "CSRF_DENIED" in logged
    assert all(
        secret not in logged
        for secret in (old_token, old_csrf, new.token, new.csrf_token, challenge, "synthetic-browser-assertion")
    )


@pytest.mark.anyio
@pytest.mark.parametrize("endpoint", ("options", "complete"))
@pytest.mark.parametrize(
    ("origin", "content_type", "status", "code"),
    (
        ("https://untrusted.invalid", "application/json", 403, "ORIGIN_DENIED"),
        (None, "application/json", 403, "ORIGIN_DENIED"),
        (ORIGIN, "text/plain", 415, "UNSUPPORTED_CONTENT_TYPE"),
    ),
)
async def test_passkey_login_still_requires_exact_origin_and_json(
    endpoint: str, origin: str | None, content_type: str, status: int, code: str
) -> None:
    container, repository, service = _container()
    headers = {CSRF_HEADER: "c" * 43, "content-type": content_type}
    if origin is not None:
        headers["origin"] = origin
    async with AsyncClient(transport=ASGITransport(app=create_app(container=container)), base_url=ORIGIN) as client:
        client.cookies.set(SESSION_COOKIE_NAME, "s" * 43, domain="nexora.private", path="/")
        denied = await client.post(f"/v1/auth/authentication/{endpoint}", headers=headers, content="{}")

    assert denied.status_code == status
    assert denied.json()["error"]["code"] == code
    assert denied.headers.get_list("set-cookie") == []
    service.begin_authentication.assert_not_called()
    service.complete_authentication.assert_not_called()
    repository.authenticate_session.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("endpoint", ("options", "complete"))
async def test_fresh_passkey_login_still_uses_the_production_request_limit(endpoint: str) -> None:
    container, repository, service = _container()
    container = replace(
        container,
        settings=RuntimeSettings(
            environment=RuntimeEnvironment.PRODUCTION,
            deployment_profile=DeploymentProfile.PRIVATE_SINGLE_HOST,
            api_host="0.0.0.0",
        ),
    )
    repository.authenticate_session.side_effect = AuthenticationDenied("fixture session denied")
    app = create_app(container=container)
    app.state.interactive_request_gate = InteractiveRequestGate(sustained_per_second=10, burst=1, clock=lambda: 100.0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
        client.cookies.set(SESSION_COOKIE_NAME, "s" * 43, domain="nexora.private", path="/")
        assert (await client.get("/v1/auth/session")).status_code == 401
        limited = await client.post(f"/v1/auth/authentication/{endpoint}", headers={"origin": ORIGIN}, json={})

    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "1"
    assert limited.json()["error"]["code"] == "INTERACTIVE_RATE_LIMITED"
    service.begin_authentication.assert_not_called()
    service.complete_authentication.assert_not_called()


@pytest.mark.anyio
async def test_rejected_passkey_does_not_replace_cookies_or_restore_private_access() -> None:
    container, repository, service = _container()
    repository.authenticate_session.side_effect = AuthenticationDenied("fixture session denied")
    service.complete_authentication.side_effect = AuthenticationDenied("fixture assertion denied")
    prior = "s" * 43
    async with AsyncClient(transport=ASGITransport(app=create_app(container=container)), base_url=ORIGIN) as client:
        client.cookies.set(SESSION_COOKIE_NAME, prior, domain="nexora.private", path="/")
        response = await client.post(
            "/v1/auth/authentication/complete",
            headers={"origin": ORIGIN},
            json={"credential_id": "fixture-credential-id", "challenge": "q" * 43, "response_json": "{}"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_DENIED"
        assert response.headers.get_list("set-cookie") == []
        assert client.cookies.get(SESSION_COOKIE_NAME) == prior
        assert (await client.get("/v1/auth/session")).status_code == 401
    service.complete_authentication.assert_called_once()


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
    application = create_app(container=container)
    headers = {"origin": ORIGIN, "content-type": "application/json"}

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        denied = await client.post("/v1/auth/registration/options", headers=headers, json={})
        reauthentication = await client.post("/v1/auth/reauthentication/options", headers=headers, json={})
        accepted = await client.post(
            "/v1/auth/logout-all",
            headers={**headers, CSRF_HEADER: "c" * 43},
            json={},
        )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "CSRF_DENIED"
    assert reauthentication.status_code == 403
    assert reauthentication.json()["error"]["code"] == "CSRF_DENIED"
    assert accepted.status_code == 200
    repository.require_recent_reauthentication.assert_called_once_with(session_id=SESSION_ID)
    repository.revoke_all_sessions.assert_called_once_with(owner_id=OWNER_ID)
    service.begin_registration.assert_not_called()
    service.begin_reauthentication.assert_not_called()


@pytest.mark.anyio
async def test_authenticated_export_download_is_owner_scoped_and_integrity_labelled() -> None:
    container, repository, _ = _container()
    session = AuthenticatedSession(
        session_id=SESSION_ID,
        owner_id=OWNER_ID,
        rotation_required=False,
        recently_reauthenticated=True,
    )
    repository.authenticate_session.return_value = session
    content = b"deterministic-export"
    key = ArtifactKey(
        owner_id=OWNER_ID,
        namespace=ArtifactNamespace.EXPORT,
        artifact_type="portfolio-export",
        artifact_id="export-01",
        version="v1",
    )
    manifest = ArtifactManifest(
        key=key,
        file_name='portfolio export".zip',
        media_type="application/zip",
        content_schema_version="nexora-export-bundle-v1",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        retention_class=RetentionClass.PINNED_EXPORT,
        published_at=datetime(2026, 10, 27, tzinfo=UTC),
    )
    storage = Mock()
    storage.read.return_value = StoredArtifact(manifest=manifest, content=content)
    application = create_app(container=replace(container, artifact_storage=storage))

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        response = await client.get("/v1/exports/portfolio-export/export-01/versions/v1/download")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-length"] == str(len(content))
    assert response.headers["x-artifact-sha256"] == manifest.sha256
    assert response.headers["content-disposition"].startswith('attachment; filename="portfolio_export_.zip"')
    assert "filename*=UTF-8''portfolio%20export%22.zip" in response.headers["content-disposition"]
    storage.read.assert_called_once_with(key)


@pytest.mark.anyio
async def test_export_download_requires_session_and_hides_missing_artifact() -> None:
    container, repository, _ = _container()
    repository.authenticate_session.return_value = AuthenticatedSession(
        session_id=SESSION_ID,
        owner_id=OWNER_ID,
        rotation_required=False,
        recently_reauthenticated=True,
    )
    storage = Mock()
    storage.read.side_effect = ArtifactNotFound("not found")
    application = create_app(container=replace(container, artifact_storage=storage))

    async with AsyncClient(transport=ASGITransport(app=application), base_url=ORIGIN) as client:
        denied = await client.get("/v1/exports/portfolio-export/export-01/versions/v1/download")
        client.cookies.set("__Host-nexora_session", "s" * 43, domain="nexora.private", path="/")
        missing = await client.get("/v1/exports/portfolio-export/export-01/versions/v1/download")

    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "AUTHENTICATION_DENIED"
    assert missing.status_code == 404
    assert missing.json()["error"] == {"code": "ARTIFACT_NOT_FOUND", "message": "artifact is unavailable"}
