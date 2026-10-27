from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Literal
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from nexora import __version__
from nexora.adapters.postgresql import RUNTIME_DATABASE_DSN_FILE_ENV, PostgreSQLIdentityRepository, probe_database
from nexora.composition import (
    PRIVATE_RUNTIME_ENVIRONMENT_VARIABLES,
    ApplicationContainer,
    compose_application,
    compose_private_application,
)
from nexora.config import RuntimeSettings, load_settings
from nexora.identity import (
    SESSION_COOKIE_NAME,
    AuthenticatedSession,
    AuthenticationDenied,
    CeremonyUnavailable,
    IdentityError,
    IssuedSession,
    verify_exact_origin,
)
from nexora.identity_service import OwnerIdentityService
from nexora.observability import (
    DependencyReadiness,
    ReadinessSnapshot,
    configure_structured_logging,
    database_pool_values,
    load_observability_settings,
)
from nexora.runtime_contracts import (
    ActionRequest,
    ActionResponse,
    AuthenticationCompleteRequest,
    AuthenticationOptionsResponse,
    AuthenticatorDescriptor,
    BootstrapCompleteRequest,
    BootstrapCompleteResponse,
    BootstrapOptionsRequest,
    ErrorDetail,
    ErrorEnvelope,
    RecoveryCompleteRequest,
    RecoveryOptionsRequest,
    RegistrationCompleteRequest,
    RegistrationOptionsResponse,
    SessionResponse,
    VersionResponse,
)
from nexora.security_config import SecuritySettings

CORRELATION_HEADER = "X-Correlation-ID"
CSRF_HEADER = "X-CSRF-Token"


class LivenessResponse(BaseModel):
    status: str
    service: str
    version: str


def _correlation_id(request: Request) -> UUID:
    supplied = request.headers.get(CORRELATION_HEADER)
    if supplied is None:
        return uuid4()
    try:
        return UUID(supplied)
    except ValueError:
        return uuid4()


def _error_response(request: Request, *, status_code: int, code: str, message: str) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", uuid4())
    request.state.reason_code = code
    payload = ErrorEnvelope(
        correlation_id=correlation_id,
        error=ErrorDetail(code=code, message=message),
    )
    return JSONResponse(payload.model_dump(mode="json"), status_code=status_code)


def _security_headers(response: Response, correlation_id: UUID) -> Response:
    nonce = secrets.token_urlsafe(18)
    response.headers[CORRELATION_HEADER] = str(correlation_id)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
        f"form-action 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'nonce-{nonce}'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; manifest-src 'self'; "
        "worker-src 'self'; upgrade-insecure-requests"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    if "Server" in response.headers:
        del response.headers["Server"]
    if "X-Powered-By" in response.headers:
        del response.headers["X-Powered-By"]
    return response


def _set_session_cookie(response: Response, issued: IssuedSession) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=issued.token,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )


def create_app(
    settings: RuntimeSettings | None = None,
    *,
    container: ApplicationContainer | None = None,
) -> FastAPI:
    if settings is not None and container is not None:
        raise ValueError("settings and container cannot both be supplied")
    resolved_container = compose_application(settings) if container is None else container

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if resolved_container.trd_bot_client is not None:
                resolved_container.trd_bot_client.close()
            if resolved_container.database_engine is not None:
                resolved_container.database_engine.dispose()

    application = FastAPI(
        docs_url=None,
        lifespan=lifespan,
        redoc_url=None,
        responses={
            status_code: {"model": ErrorEnvelope, "description": "Versioned fail-closed error"}
            for status_code in (400, 401, 403, 404, 409, 413, 415, 422, 500, 503)
        },
        title="Nexora API",
        version=__version__,
    )
    application.state.container = resolved_container

    @application.exception_handler(RequestValidationError)
    async def request_validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
        return _error_response(
            request,
            status_code=422,
            code="REQUEST_VALIDATION_FAILED",
            message="request validation failed",
        )

    @application.exception_handler(AuthenticationDenied)
    async def authentication_denied(request: Request, _: AuthenticationDenied) -> JSONResponse:
        return _error_response(request, status_code=401, code="AUTHENTICATION_DENIED", message="request denied")

    @application.exception_handler(CeremonyUnavailable)
    async def ceremony_unavailable(request: Request, _: CeremonyUnavailable) -> JSONResponse:
        return _error_response(
            request,
            status_code=503,
            code="AUTHENTICATION_UNAVAILABLE",
            message="authentication service is unavailable",
        )

    @application.exception_handler(IdentityError)
    async def identity_error(request: Request, _: IdentityError) -> JSONResponse:
        return _error_response(request, status_code=409, code="IDENTITY_STATE_CONFLICT", message="request denied")

    @application.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
        return _error_response(
            request,
            status_code=error.status_code,
            code=f"HTTP_{error.status_code}",
            message="resource is unavailable" if error.status_code == 404 else "request failed",
        )

    @application.exception_handler(Exception)
    async def unhandled_error(request: Request, _: Exception) -> JSONResponse:
        return _error_response(
            request,
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message="request could not be completed",
        )

    @application.middleware("http")
    async def security_boundary(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = _correlation_id(request)
        request.state.correlation_id = correlation_id
        supplied_correlation = request.headers.get(CORRELATION_HEADER)
        if supplied_correlation is not None and supplied_correlation != str(correlation_id):
            return _security_headers(
                _error_response(
                    request,
                    status_code=400,
                    code="INVALID_CORRELATION_ID",
                    message="correlation ID is invalid",
                ),
                correlation_id,
            )
        if resolved_container.security is not None and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            try:
                verify_exact_origin(request.headers.get("origin"), resolved_container.security.canonical_origin)
            except AuthenticationDenied:
                return _security_headers(
                    _error_response(request, status_code=403, code="ORIGIN_DENIED", message="request denied"),
                    correlation_id,
                )
            content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                return _security_headers(
                    _error_response(
                        request,
                        status_code=415,
                        code="UNSUPPORTED_CONTENT_TYPE",
                        message="mutations require application/json",
                    ),
                    correlation_id,
                )
            session_token = request.cookies.get(SESSION_COOKIE_NAME)
            if session_token is not None:
                csrf_token = request.headers.get(CSRF_HEADER)
                repository = resolved_container.identity_repository
                if repository is None or csrf_token is None:
                    return _security_headers(
                        _error_response(request, status_code=403, code="CSRF_DENIED", message="request denied"),
                        correlation_id,
                    )
                try:
                    repository.authenticate_session(token=session_token, csrf_token=csrf_token)
                except AuthenticationDenied:
                    return _security_headers(
                        _error_response(request, status_code=403, code="CSRF_DENIED", message="request denied"),
                        correlation_id,
                    )
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                too_large = int(content_length) > 1_048_576
            except ValueError:
                return _security_headers(
                    _error_response(
                        request,
                        status_code=400,
                        code="INVALID_CONTENT_LENGTH",
                        message="content length is invalid",
                    ),
                    correlation_id,
                )
            if too_large:
                return _security_headers(
                    _error_response(
                        request,
                        status_code=413,
                        code="REQUEST_BODY_TOO_LARGE",
                        message="request body is too large",
                    ),
                    correlation_id,
                )
        response = await call_next(request)
        return _security_headers(response, correlation_id)

    @application.middleware("http")
    async def observability_boundary(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = perf_counter()
        response = await call_next(request)
        duration_ms = (perf_counter() - started) * 1_000
        route_object = request.scope.get("route")
        route_path = getattr(route_object, "path", "<unmatched>")
        correlation_id = str(getattr(request.state, "correlation_id", uuid4()))
        reason_code = getattr(request.state, "reason_code", "REQUEST_COMPLETED")
        resolved_container.observability.observe_request(
            method=request.method,
            route=route_path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
            reason_code=reason_code,
        )
        return response

    def identity_runtime() -> tuple[OwnerIdentityService, PostgreSQLIdentityRepository, SecuritySettings]:
        service = resolved_container.owner_identity_service
        repository = resolved_container.identity_repository
        security = resolved_container.security
        if service is None or repository is None or security is None:
            raise CeremonyUnavailable("identity runtime is not configured")
        return service, repository, security

    def require_session(request: Request) -> tuple[str, AuthenticatedSession]:
        _, repository, _ = identity_runtime()
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token is None:
            raise AuthenticationDenied("session is required")
        return token, repository.authenticate_session(token=token)

    @application.get("/health/live", response_model=LivenessResponse, operation_id="getLiveness")
    def liveness() -> LivenessResponse:
        return LivenessResponse(status="ok", service="nexora-api", version=__version__)

    @application.get("/health/ready", include_in_schema=False)
    def readiness() -> Response:
        engine = resolved_container.database_engine
        database_ready = False
        if engine is not None:
            try:
                database_ready = probe_database(engine)
            except Exception:
                database_ready = False
            if database_ready:
                try:
                    resolved_container.observability.metrics.update_database_pool(database_pool_values(engine))
                except ValueError:
                    resolved_container.observability.metrics.update_database_pool(None)

        identity_ready = all(
            component is not None
            for component in (
                resolved_container.identity_repository,
                resolved_container.owner_identity_service,
                resolved_container.security,
            )
        )
        trd_ready = resolved_container.trd_bot_client is not None
        if engine is None:
            database = DependencyReadiness(status="not_configured", reason_code="DATABASE_NOT_CONFIGURED")
        elif database_ready:
            database = DependencyReadiness(status="ready", reason_code="DATABASE_READY")
        else:
            database = DependencyReadiness(status="unavailable", reason_code="DATABASE_UNAVAILABLE")
        identity = DependencyReadiness(
            status="ready" if identity_ready else "not_configured",
            reason_code="IDENTITY_RUNTIME_READY" if identity_ready else "IDENTITY_NOT_CONFIGURED",
        )
        trd_bot = DependencyReadiness(
            status="ready" if trd_ready else "not_configured",
            reason_code="TRD_BOT_ADAPTER_READY" if trd_ready else "TRD_BOT_NOT_CONFIGURED",
        )
        overall_status: Literal["ready", "not_configured", "unavailable"] = (
            "unavailable"
            if engine is not None and not database_ready
            else "ready"
            if database_ready and identity_ready and trd_ready
            else "not_configured"
        )
        snapshot = ReadinessSnapshot(
            status=overall_status,
            dependencies={
                "database": database,
                "identity": identity,
                "trd_bot": trd_bot,
            },
        )
        return JSONResponse(snapshot.model_dump(mode="json"), status_code=200 if overall_status == "ready" else 503)

    @application.get("/version", response_model=VersionResponse, operation_id="getVersion")
    def version() -> VersionResponse:
        identity = resolved_container.identity
        return VersionResponse(
            service="nexora-api",
            version=identity.version,
            commit_sha=identity.commit_sha,
            configuration_schema=identity.configuration_schema,
            configuration_checksum=identity.configuration_checksum,
        )

    @application.post(
        "/v1/auth/bootstrap/options",
        response_model=RegistrationOptionsResponse,
        operation_id="createBootstrapOptions",
    )
    def bootstrap_options(payload: BootstrapOptionsRequest) -> RegistrationOptionsResponse:
        _, _, security = identity_runtime()
        return RegistrationOptionsResponse(challenge=payload.bootstrap_token, rp_id=security.rp_id)

    @application.post(
        "/v1/auth/bootstrap/complete",
        response_model=BootstrapCompleteResponse,
        operation_id="completeBootstrap",
    )
    def complete_bootstrap(payload: BootstrapCompleteRequest) -> BootstrapCompleteResponse:
        service, _, _ = identity_runtime()
        owner_id, recovery_codes = service.complete_initial_registration(
            bootstrap_token=payload.bootstrap_token,
            response_json=payload.response_json,
        )
        return BootstrapCompleteResponse(owner_id=owner_id, recovery_codes=list(recovery_codes))

    def authentication_options_payload() -> AuthenticationOptionsResponse:
        service, _, security = identity_runtime()
        _, challenge, credentials = service.begin_authentication()
        return AuthenticationOptionsResponse(
            challenge=challenge,
            rp_id=security.rp_id,
            allow_credentials=[
                AuthenticatorDescriptor(credential_id=item.credential_id, transports=list(item.transports))
                for item in credentials
            ],
        )

    @application.post(
        "/v1/auth/authentication/options",
        response_model=AuthenticationOptionsResponse,
        operation_id="createAuthenticationOptions",
    )
    def authentication_options(_payload: ActionRequest) -> AuthenticationOptionsResponse:
        return authentication_options_payload()

    @application.post(
        "/v1/auth/authentication/complete",
        response_model=SessionResponse,
        operation_id="completeAuthentication",
    )
    def complete_authentication(payload: AuthenticationCompleteRequest, response: Response) -> SessionResponse:
        service, _, _ = identity_runtime()
        issued = service.complete_authentication(
            credential_id=payload.credential_id,
            challenge=payload.challenge,
            response_json=payload.response_json,
        )
        _set_session_cookie(response, issued)
        return SessionResponse(
            owner_id=issued.owner_id,
            csrf_token=issued.csrf_token,
            idle_expires_at=issued.idle_expires_at,
            absolute_expires_at=issued.absolute_expires_at,
            rotation_required=False,
            recently_reauthenticated=True,
        )

    @application.get("/v1/auth/session", response_model=SessionResponse, operation_id="getSession")
    def get_session(request: Request) -> SessionResponse:
        _, session = require_session(request)
        return SessionResponse(
            owner_id=session.owner_id,
            rotation_required=session.rotation_required,
            recently_reauthenticated=session.recently_reauthenticated,
        )

    @application.post("/v1/auth/session/rotate", response_model=SessionResponse, operation_id="rotateSession")
    def rotate_session(_payload: ActionRequest, request: Request, response: Response) -> SessionResponse:
        token, _ = require_session(request)
        _, repository, _ = identity_runtime()
        csrf = request.headers.get(CSRF_HEADER)
        if csrf is None:
            raise AuthenticationDenied("CSRF token is required")
        issued = repository.rotate_session(token=token, csrf_token=csrf)
        rotated = repository.authenticate_session(token=issued.token)
        _set_session_cookie(response, issued)
        return SessionResponse(
            owner_id=issued.owner_id,
            csrf_token=issued.csrf_token,
            idle_expires_at=issued.idle_expires_at,
            absolute_expires_at=issued.absolute_expires_at,
            rotation_required=False,
            recently_reauthenticated=rotated.recently_reauthenticated,
        )

    @application.post(
        "/v1/auth/reauthentication/options",
        response_model=AuthenticationOptionsResponse,
        operation_id="createReauthenticationOptions",
    )
    def reauthentication_options(_payload: ActionRequest, request: Request) -> AuthenticationOptionsResponse:
        token, _ = require_session(request)
        service, _, security = identity_runtime()
        _, challenge, credentials = service.begin_reauthentication(session_token=token)
        return AuthenticationOptionsResponse(
            challenge=challenge,
            rp_id=security.rp_id,
            allow_credentials=[
                AuthenticatorDescriptor(credential_id=item.credential_id, transports=list(item.transports))
                for item in credentials
            ],
        )

    @application.post(
        "/v1/auth/reauthentication/complete",
        response_model=SessionResponse,
        operation_id="completeReauthentication",
    )
    def complete_reauthentication(payload: AuthenticationCompleteRequest, request: Request) -> SessionResponse:
        token, _ = require_session(request)
        service, _, _ = identity_runtime()
        session = service.complete_reauthentication(
            session_token=token,
            credential_id=payload.credential_id,
            challenge=payload.challenge,
            response_json=payload.response_json,
        )
        return SessionResponse(
            owner_id=session.owner_id,
            rotation_required=session.rotation_required,
            recently_reauthenticated=session.recently_reauthenticated,
        )

    @application.post(
        "/v1/auth/registration/options",
        response_model=RegistrationOptionsResponse,
        operation_id="createRegistrationOptions",
    )
    def registration_options(_payload: ActionRequest, request: Request) -> RegistrationOptionsResponse:
        token, _ = require_session(request)
        service, _, security = identity_runtime()
        session, challenge = service.begin_registration(session_token=token)
        return RegistrationOptionsResponse(
            owner_id=session.owner_id,
            challenge=challenge,
            rp_id=security.rp_id,
        )

    @application.post(
        "/v1/auth/registration/complete",
        response_model=ActionResponse,
        operation_id="completeRegistration",
    )
    def complete_registration(payload: RegistrationCompleteRequest, request: Request) -> ActionResponse:
        token, _ = require_session(request)
        service, _, _ = identity_runtime()
        service.complete_registration(
            session_token=token,
            challenge=payload.challenge,
            response_json=payload.response_json,
        )
        return ActionResponse(status="completed")

    @application.post(
        "/v1/auth/recovery/options",
        response_model=RegistrationOptionsResponse,
        operation_id="createRecoveryOptions",
    )
    def recovery_options(payload: RecoveryOptionsRequest) -> RegistrationOptionsResponse:
        service, _, security = identity_runtime()
        owner_id, challenge = service.recover(recovery_code=payload.recovery_code)
        return RegistrationOptionsResponse(
            owner_id=owner_id,
            challenge=challenge,
            rp_id=security.rp_id,
        )

    @application.post(
        "/v1/auth/recovery/complete",
        response_model=SessionResponse,
        operation_id="completeRecovery",
    )
    def complete_recovery(payload: RecoveryCompleteRequest, response: Response) -> SessionResponse:
        service, _, _ = identity_runtime()
        issued = service.complete_recovery_registration(
            owner_id=payload.owner_id,
            challenge=payload.challenge,
            response_json=payload.response_json,
        )
        _set_session_cookie(response, issued)
        return SessionResponse(
            owner_id=issued.owner_id,
            csrf_token=issued.csrf_token,
            idle_expires_at=issued.idle_expires_at,
            absolute_expires_at=issued.absolute_expires_at,
            rotation_required=False,
            recently_reauthenticated=True,
        )

    @application.post("/v1/auth/logout", response_model=ActionResponse, operation_id="logout")
    def logout(_payload: ActionRequest, request: Request, response: Response) -> ActionResponse:
        token, _ = require_session(request)
        _, repository, _ = identity_runtime()
        repository.revoke_session(token=token)
        _clear_session_cookie(response)
        return ActionResponse(status="completed")

    @application.post("/v1/auth/logout-all", response_model=ActionResponse, operation_id="logoutAll")
    def logout_all(_payload: ActionRequest, request: Request, response: Response) -> ActionResponse:
        _, session = require_session(request)
        _, repository, _ = identity_runtime()
        repository.require_recent_reauthentication(session_id=session.session_id)
        repository.revoke_all_sessions(owner_id=session.owner_id)
        _clear_session_cookie(response)
        return ActionResponse(status="completed")

    return application


app = create_app(load_settings(os.environ, permitted_external_variables=PRIVATE_RUNTIME_ENVIRONMENT_VARIABLES))


def run() -> None:
    if RUNTIME_DATABASE_DSN_FILE_ENV in os.environ:
        container = compose_private_application(environ=os.environ)
        settings = container.settings
        application = create_app(container=container)
    else:
        observability_settings = load_observability_settings(os.environ, production=False)
        settings = load_settings()
        container = compose_application(settings, observability_settings=observability_settings)
        application = create_app(container=container)
    configure_structured_logging(container.observability, level=settings.log_level.value)
    uvicorn.run(application, host=settings.api_host, port=settings.api_port, reload=False)
