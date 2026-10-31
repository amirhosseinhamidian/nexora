from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Literal
from urllib.parse import quote
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from nexora import __version__
from nexora.adapters.postgresql import (
    RUNTIME_DATABASE_DSN_FILE_ENV,
    ImportReconciliationRepository,
    PortfolioRegistryRepository,
    PostgreSQLIdentityRepository,
    TransactionJournalRepository,
    probe_database,
)
from nexora.adapters.trd_bot import TrdBotIntegrationMode
from nexora.artifact_storage import (
    ArtifactIntegrityError,
    ArtifactKey,
    ArtifactNamespace,
    ArtifactNotFound,
    ArtifactStorageError,
    ArtifactValidationError,
)
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
from nexora.import_contracts import (
    ImportBatchListResponse,
    ImportBatchResponse,
    ImportDryRunRequest,
    ImportReviewRequest,
    ImportRowResponse,
    ReconciliationCaseListResponse,
    ReconciliationCaseResponse,
    ReconciliationDecisionRequest,
)
from nexora.import_reconciliation import (
    ImportBatchView,
    ImportConflict,
    ImportNotFound,
    ImportValidationError,
    ReconciliationCaseView,
)
from nexora.observability import (
    DependencyReadiness,
    ReadinessSnapshot,
    configure_structured_logging,
    database_pool_values,
    load_observability_settings,
)
from nexora.overload import InteractiveRequestGate
from nexora.portfolio_contracts import (
    AccountListResponse,
    AccountResponse,
    AssetIdentifierResponse,
    AssetListResponse,
    AssetResponse,
    CreateAccountRequest,
    CreateAssetIdentifierRequest,
    CreateAssetRequest,
    CreatePortfolioRequest,
    LifecycleRequest,
    PortfolioListResponse,
    PortfolioResponse,
)
from nexora.portfolio_registry import RegistryConflict, RegistryNotFound
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
from nexora.transaction_contracts import (
    CreateTransactionRequest,
    ReverseTransactionRequest,
    SupersedeTransactionRequest,
    TransactionLegResponse,
    TransactionListResponse,
    TransactionResponse,
)
from nexora.transaction_journal import (
    JournalConflict,
    JournalNotFound,
    JournalValidationError,
    TransactionLegInput,
    TransactionView,
    canonical_quantity,
    normalize_quantity,
)

CORRELATION_HEADER = "X-Correlation-ID"
CSRF_HEADER = "X-CSRF-Token"
CSRF_COOKIE_NAME = "__Host-nexora_csrf"


class LivenessResponse(BaseModel):
    status: str
    service: str
    version: str


def _transaction_response(transaction: TransactionView) -> TransactionResponse:
    return TransactionResponse(
        transaction_id=transaction.transaction_id,
        portfolio_id=transaction.portfolio_id,
        transaction_kind=transaction.transaction_kind,
        idempotency_key=transaction.idempotency_key,
        occurred_at=transaction.occurred_at,
        recorded_at=transaction.recorded_at,
        source_kind=transaction.source_kind,
        source_reference=transaction.source_reference,
        source_payload_sha256=transaction.source_payload_sha256,
        request_sha256=transaction.request_sha256,
        memo=transaction.memo,
        correction_of_transaction_id=transaction.correction_of_transaction_id,
        correction_kind=transaction.correction_kind,
        correction_reason=transaction.correction_reason,
        legs=[
            TransactionLegResponse(
                transaction_leg_id=leg.transaction_leg_id,
                sequence=leg.sequence,
                account_id=leg.account_id,
                external_counterparty=leg.external_counterparty,
                asset_id=leg.asset_id,
                quantity=canonical_quantity(leg.quantity),
                memo=leg.memo,
            )
            for leg in transaction.legs
        ],
    )


def _import_batch_response(batch: ImportBatchView) -> ImportBatchResponse:
    return ImportBatchResponse(
        import_batch_id=batch.import_batch_id,
        source_format=batch.source_format,
        content_sha256=batch.content_sha256,
        status=batch.status,
        row_count=batch.row_count,
        ready_count=batch.ready_count,
        duplicate_count=batch.duplicate_count,
        quarantined_count=batch.quarantined_count,
        review_reason=batch.review_reason,
        created_at=batch.created_at,
        reviewed_at=batch.reviewed_at,
        published_at=batch.published_at,
        rows=[ImportRowResponse.model_validate(row) for row in batch.rows],
    )


def _reconciliation_response(case: ReconciliationCaseView) -> ReconciliationCaseResponse:
    return ReconciliationCaseResponse.model_validate(case)


def _transaction_legs(
    payload: CreateTransactionRequest | SupersedeTransactionRequest,
) -> tuple[TransactionLegInput, ...]:
    return tuple(
        TransactionLegInput(
            account_id=leg.account_id,
            external_counterparty=leg.external_counterparty,
            asset_id=leg.asset_id,
            quantity=normalize_quantity(leg.quantity),
            memo=leg.memo,
        )
        for leg in payload.legs
    )


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


def _set_session_cookies(response: Response, issued: IssuedSession) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=issued.token,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=issued.csrf_token,
        path="/",
        secure=True,
        httponly=False,
        samesite="strict",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=False,
        samesite="strict",
    )


def _download_disposition(file_name: str) -> str:
    ascii_name = "".join(
        character if character.isascii() and (character.isalnum() or character in "._-") else "_"
        for character in file_name
    )
    if not ascii_name or ascii_name in {".", ".."}:
        ascii_name = "nexora-export.bin"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(file_name, safe='')}"


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
            for status_code in (400, 401, 403, 404, 409, 413, 415, 422, 429, 500, 503)
        },
        title="Nexora API",
        version=__version__,
    )
    application.state.container = resolved_container
    application.state.interactive_request_gate = InteractiveRequestGate()

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

    @application.exception_handler(RegistryNotFound)
    async def registry_not_found(request: Request, _: RegistryNotFound) -> JSONResponse:
        return _error_response(
            request,
            status_code=404,
            code="REGISTRY_RESOURCE_NOT_FOUND",
            message="registry resource is unavailable",
        )

    @application.exception_handler(RegistryConflict)
    async def registry_conflict(request: Request, _: RegistryConflict) -> JSONResponse:
        return _error_response(
            request,
            status_code=409,
            code="REGISTRY_STATE_CONFLICT",
            message="registry state changed or conflicts with an existing resource",
        )

    @application.exception_handler(JournalNotFound)
    async def journal_not_found(request: Request, _: JournalNotFound) -> JSONResponse:
        return _error_response(
            request,
            status_code=404,
            code="JOURNAL_RESOURCE_NOT_FOUND",
            message="journal resource is unavailable",
        )

    @application.exception_handler(JournalConflict)
    async def journal_conflict(request: Request, _: JournalConflict) -> JSONResponse:
        return _error_response(
            request,
            status_code=409,
            code="JOURNAL_STATE_CONFLICT",
            message="journal state conflicts with the requested append",
        )

    @application.exception_handler(JournalValidationError)
    async def journal_validation_error(request: Request, _: JournalValidationError) -> JSONResponse:
        return _error_response(
            request,
            status_code=422,
            code="JOURNAL_VALIDATION_FAILED",
            message="transaction journal validation failed",
        )

    @application.exception_handler(ImportNotFound)
    async def import_not_found(request: Request, _: ImportNotFound) -> JSONResponse:
        return _error_response(
            request,
            status_code=404,
            code="IMPORT_RESOURCE_NOT_FOUND",
            message="import or reconciliation evidence is unavailable",
        )

    @application.exception_handler(ImportConflict)
    async def import_conflict(request: Request, _: ImportConflict) -> JSONResponse:
        return _error_response(
            request,
            status_code=409,
            code="IMPORT_STATE_CONFLICT",
            message="import or reconciliation state conflicts with the requested transition",
        )

    @application.exception_handler(ImportValidationError)
    async def import_validation_error(request: Request, _: ImportValidationError) -> JSONResponse:
        return _error_response(
            request,
            status_code=422,
            code="IMPORT_VALIDATION_FAILED",
            message="import or reconciliation validation failed",
        )

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
        if resolved_container.settings.environment.value == "production" and request.url.path.startswith("/v1/"):
            overload = application.state.interactive_request_gate.acquire()
            if not overload.allowed:
                overload_response = _error_response(
                    request,
                    status_code=429,
                    code="INTERACTIVE_RATE_LIMITED",
                    message="request capacity is temporarily unavailable",
                )
                overload_response.headers["Retry-After"] = str(overload.retry_after_seconds)
                return _security_headers(overload_response, correlation_id)
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

    def portfolio_registry() -> PortfolioRegistryRepository:
        repository = resolved_container.portfolio_registry_repository
        if repository is None:
            raise CeremonyUnavailable("portfolio registry is not configured")
        return repository

    def transaction_journal() -> TransactionJournalRepository:
        repository = resolved_container.transaction_journal_repository
        if repository is None:
            raise CeremonyUnavailable("transaction journal is not configured")
        return repository

    def import_reconciliation() -> ImportReconciliationRepository:
        repository = resolved_container.import_reconciliation_repository
        if repository is None:
            raise CeremonyUnavailable("import and reconciliation runtime is not configured")
        return repository

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
        trd_disabled = (
            resolved_container.trd_bot_integration_mode is TrdBotIntegrationMode.DISABLED_INCOMPATIBLE_PROVIDER
        )
        trd_ready = trd_disabled or resolved_container.trd_bot_client is not None
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
            status="not_configured" if trd_disabled else "ready" if trd_ready else "not_configured",
            reason_code=(
                "TRD_BOT_DISABLED_INCOMPATIBLE_PROVIDER"
                if trd_disabled
                else "TRD_BOT_ADAPTER_READY"
                if trd_ready
                else "TRD_BOT_NOT_CONFIGURED"
            ),
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
        _set_session_cookies(response, issued)
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
        _set_session_cookies(response, issued)
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
        _set_session_cookies(response, issued)
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
        _clear_session_cookies(response)
        return ActionResponse(status="completed")

    @application.post("/v1/auth/logout-all", response_model=ActionResponse, operation_id="logoutAll")
    def logout_all(_payload: ActionRequest, request: Request, response: Response) -> ActionResponse:
        _, session = require_session(request)
        _, repository, _ = identity_runtime()
        repository.require_recent_reauthentication(session_id=session.session_id)
        repository.revoke_all_sessions(owner_id=session.owner_id)
        _clear_session_cookies(response)
        return ActionResponse(status="completed")

    @application.post("/v1/assets", response_model=AssetResponse, status_code=201, operation_id="createAsset")
    def create_asset(payload: CreateAssetRequest, request: Request) -> AssetResponse:
        _, session = require_session(request)
        created = portfolio_registry().create_asset(
            owner_id=session.owner_id,
            asset_key=payload.asset_key,
            symbol=payload.symbol,
            name=payload.name,
            asset_class=payload.asset_class,
            precision=payload.precision,
        )
        return AssetResponse.model_validate(created)

    @application.get("/v1/assets", response_model=AssetListResponse, operation_id="listAssets")
    def list_assets(request: Request) -> AssetListResponse:
        _, session = require_session(request)
        assets = portfolio_registry().list_assets(owner_id=session.owner_id)
        return AssetListResponse(items=[AssetResponse.model_validate(asset) for asset in assets])

    @application.post(
        "/v1/assets/{asset_id}/identifiers",
        response_model=AssetIdentifierResponse,
        status_code=201,
        operation_id="createAssetIdentifier",
    )
    def create_asset_identifier(
        asset_id: UUID,
        payload: CreateAssetIdentifierRequest,
        request: Request,
    ) -> AssetIdentifierResponse:
        _, session = require_session(request)
        created = portfolio_registry().add_asset_identifier(
            owner_id=session.owner_id,
            asset_id=asset_id,
            scheme=payload.scheme,
            value=payload.value,
            is_primary=payload.is_primary,
        )
        return AssetIdentifierResponse.model_validate(created)

    @application.post(
        "/v1/assets/{asset_id}/deactivate",
        response_model=AssetResponse,
        operation_id="deactivateAsset",
    )
    def deactivate_asset(asset_id: UUID, payload: LifecycleRequest, request: Request) -> AssetResponse:
        _, session = require_session(request)
        changed = portfolio_registry().deactivate_asset(
            owner_id=session.owner_id,
            asset_id=asset_id,
            expected_row_version=payload.expected_row_version,
        )
        return AssetResponse.model_validate(changed)

    @application.post(
        "/v1/portfolios",
        response_model=PortfolioResponse,
        status_code=201,
        operation_id="createPortfolio",
    )
    def create_portfolio(payload: CreatePortfolioRequest, request: Request) -> PortfolioResponse:
        _, session = require_session(request)
        created = portfolio_registry().create_portfolio(
            owner_id=session.owner_id,
            portfolio_key=payload.portfolio_key,
            name=payload.name,
            kind=payload.kind,
            base_asset_id=payload.base_asset_id,
        )
        return PortfolioResponse.model_validate(created)

    @application.get("/v1/portfolios", response_model=PortfolioListResponse, operation_id="listPortfolios")
    def list_portfolios(request: Request) -> PortfolioListResponse:
        _, session = require_session(request)
        portfolios = portfolio_registry().list_portfolios(owner_id=session.owner_id)
        return PortfolioListResponse(items=[PortfolioResponse.model_validate(item) for item in portfolios])

    @application.get(
        "/v1/portfolios/{portfolio_id}",
        response_model=PortfolioResponse,
        operation_id="getPortfolio",
    )
    def get_portfolio(portfolio_id: UUID, request: Request) -> PortfolioResponse:
        _, session = require_session(request)
        portfolio = portfolio_registry().get_portfolio(owner_id=session.owner_id, portfolio_id=portfolio_id)
        return PortfolioResponse.model_validate(portfolio)

    @application.post(
        "/v1/portfolios/{portfolio_id}/archive",
        response_model=PortfolioResponse,
        operation_id="archivePortfolio",
    )
    def archive_portfolio(portfolio_id: UUID, payload: LifecycleRequest, request: Request) -> PortfolioResponse:
        _, session = require_session(request)
        changed = portfolio_registry().archive_portfolio(
            owner_id=session.owner_id,
            portfolio_id=portfolio_id,
            expected_row_version=payload.expected_row_version,
        )
        return PortfolioResponse.model_validate(changed)

    @application.post(
        "/v1/accounts",
        response_model=AccountResponse,
        status_code=201,
        operation_id="createAccount",
    )
    def create_account(payload: CreateAccountRequest, request: Request) -> AccountResponse:
        _, session = require_session(request)
        created = portfolio_registry().create_account(
            owner_id=session.owner_id,
            portfolio_id=payload.portfolio_id,
            account_key=payload.account_key,
            name=payload.name,
            kind=payload.kind,
            institution_name=payload.institution_name,
            external_reference=payload.external_reference,
        )
        return AccountResponse.model_validate(created)

    @application.get("/v1/accounts", response_model=AccountListResponse, operation_id="listAccounts")
    def list_accounts(request: Request, portfolio_id: UUID | None = None) -> AccountListResponse:
        _, session = require_session(request)
        accounts = portfolio_registry().list_accounts(owner_id=session.owner_id, portfolio_id=portfolio_id)
        return AccountListResponse(items=[AccountResponse.model_validate(item) for item in accounts])

    @application.post(
        "/v1/accounts/{account_id}/close",
        response_model=AccountResponse,
        operation_id="closeAccount",
    )
    def close_account(account_id: UUID, payload: LifecycleRequest, request: Request) -> AccountResponse:
        _, session = require_session(request)
        changed = portfolio_registry().close_account(
            owner_id=session.owner_id,
            account_id=account_id,
            expected_row_version=payload.expected_row_version,
        )
        return AccountResponse.model_validate(changed)

    @application.post(
        "/v1/transactions",
        response_model=TransactionResponse,
        status_code=201,
        operation_id="postTransaction",
    )
    def post_transaction(
        payload: CreateTransactionRequest,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160),
    ) -> TransactionResponse:
        _, session = require_session(request)
        posted = transaction_journal().post_transaction(
            owner_id=session.owner_id,
            portfolio_id=payload.portfolio_id,
            transaction_kind=payload.transaction_kind,
            idempotency_key=idempotency_key,
            occurred_at=payload.occurred_at,
            source_kind=payload.source_kind,
            source_reference=payload.source_reference,
            source_payload_sha256=payload.source_payload_sha256,
            legs=_transaction_legs(payload),
            memo=payload.memo,
        )
        return _transaction_response(posted)

    @application.get(
        "/v1/transactions",
        response_model=TransactionListResponse,
        operation_id="listTransactions",
    )
    def list_transactions(request: Request, portfolio_id: UUID | None = None) -> TransactionListResponse:
        _, session = require_session(request)
        transactions = transaction_journal().list_transactions(
            owner_id=session.owner_id,
            portfolio_id=portfolio_id,
        )
        return TransactionListResponse(items=[_transaction_response(item) for item in transactions])

    @application.get(
        "/v1/transactions/{transaction_id}",
        response_model=TransactionResponse,
        operation_id="getTransaction",
    )
    def get_transaction(transaction_id: UUID, request: Request) -> TransactionResponse:
        _, session = require_session(request)
        transaction = transaction_journal().get_transaction(
            owner_id=session.owner_id,
            transaction_id=transaction_id,
        )
        return _transaction_response(transaction)

    @application.post(
        "/v1/transactions/{transaction_id}/reversals",
        response_model=TransactionResponse,
        status_code=201,
        operation_id="reverseTransaction",
    )
    def reverse_transaction(
        transaction_id: UUID,
        payload: ReverseTransactionRequest,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160),
    ) -> TransactionResponse:
        _, session = require_session(request)
        reversal = transaction_journal().reverse_transaction(
            owner_id=session.owner_id,
            transaction_id=transaction_id,
            idempotency_key=idempotency_key,
            occurred_at=payload.occurred_at,
            source_kind=payload.source_kind,
            source_reference=payload.source_reference,
            source_payload_sha256=payload.source_payload_sha256,
            reason=payload.reason,
            memo=payload.memo,
        )
        return _transaction_response(reversal)

    @application.post(
        "/v1/transactions/{transaction_id}/supersessions",
        response_model=TransactionResponse,
        status_code=201,
        operation_id="supersedeTransaction",
    )
    def supersede_transaction(
        transaction_id: UUID,
        payload: SupersedeTransactionRequest,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160),
    ) -> TransactionResponse:
        _, session = require_session(request)
        supersession = transaction_journal().supersede_transaction(
            owner_id=session.owner_id,
            transaction_id=transaction_id,
            transaction_kind=payload.transaction_kind,
            idempotency_key=idempotency_key,
            occurred_at=payload.occurred_at,
            source_kind=payload.source_kind,
            source_reference=payload.source_reference,
            source_payload_sha256=payload.source_payload_sha256,
            legs=_transaction_legs(payload),
            reason=payload.reason,
            memo=payload.memo,
        )
        return _transaction_response(supersession)

    @application.post(
        "/v1/imports/dry-runs",
        response_model=ImportBatchResponse,
        status_code=201,
        operation_id="createImportDryRun",
    )
    def create_import_dry_run(payload: ImportDryRunRequest, request: Request) -> ImportBatchResponse:
        _, session = require_session(request)
        batch = import_reconciliation().create_dry_run(
            owner_id=session.owner_id,
            source_format=payload.source_format,
            content=payload.content,
        )
        return _import_batch_response(batch)

    @application.get(
        "/v1/imports",
        response_model=ImportBatchListResponse,
        operation_id="listImportBatches",
    )
    def list_import_batches(request: Request) -> ImportBatchListResponse:
        _, session = require_session(request)
        batches = import_reconciliation().list_batches(owner_id=session.owner_id)
        return ImportBatchListResponse(items=[_import_batch_response(batch) for batch in batches])

    @application.get(
        "/v1/imports/{import_batch_id}",
        response_model=ImportBatchResponse,
        operation_id="getImportBatch",
    )
    def get_import_batch(import_batch_id: UUID, request: Request) -> ImportBatchResponse:
        _, session = require_session(request)
        batch = import_reconciliation().get_batch(
            owner_id=session.owner_id,
            import_batch_id=import_batch_id,
        )
        return _import_batch_response(batch)

    @application.post(
        "/v1/imports/{import_batch_id}/reviews",
        response_model=ImportBatchResponse,
        operation_id="reviewImportBatch",
    )
    def review_import_batch(
        import_batch_id: UUID,
        payload: ImportReviewRequest,
        request: Request,
    ) -> ImportBatchResponse:
        _, session = require_session(request)
        batch = import_reconciliation().review_batch(
            owner_id=session.owner_id,
            import_batch_id=import_batch_id,
            reason=payload.reason,
        )
        return _import_batch_response(batch)

    @application.post(
        "/v1/imports/{import_batch_id}/publication",
        response_model=ImportBatchResponse,
        operation_id="publishImportBatch",
    )
    def publish_import_batch(
        import_batch_id: UUID,
        _payload: ActionRequest,
        request: Request,
    ) -> ImportBatchResponse:
        _, session = require_session(request)
        _, identity_repository, _ = identity_runtime()
        identity_repository.require_recent_reauthentication(session_id=session.session_id)
        batch = import_reconciliation().publish_batch(
            owner_id=session.owner_id,
            import_batch_id=import_batch_id,
        )
        return _import_batch_response(batch)

    @application.get(
        "/v1/reconciliation-cases",
        response_model=ReconciliationCaseListResponse,
        operation_id="listReconciliationCases",
    )
    def list_reconciliation_cases(request: Request) -> ReconciliationCaseListResponse:
        _, session = require_session(request)
        cases = import_reconciliation().list_reconciliation_cases(owner_id=session.owner_id)
        return ReconciliationCaseListResponse(items=[_reconciliation_response(case) for case in cases])

    @application.post(
        "/v1/reconciliation-cases/{reconciliation_case_id}/decisions",
        response_model=ReconciliationCaseResponse,
        operation_id="decideReconciliationCase",
    )
    def decide_reconciliation_case(
        reconciliation_case_id: UUID,
        payload: ReconciliationDecisionRequest,
        request: Request,
    ) -> ReconciliationCaseResponse:
        _, session = require_session(request)
        _, identity_repository, _ = identity_runtime()
        identity_repository.require_recent_reauthentication(session_id=session.session_id)
        case = import_reconciliation().decide_reconciliation_case(
            owner_id=session.owner_id,
            reconciliation_case_id=reconciliation_case_id,
            state=payload.state,
            expected_row_version=payload.expected_row_version,
            reason=payload.reason,
        )
        return _reconciliation_response(case)

    @application.get(
        "/v1/exports/{artifact_type}/{artifact_id}/versions/{version}/download",
        include_in_schema=False,
    )
    def download_export(
        artifact_type: str,
        artifact_id: str,
        version: str,
        request: Request,
    ) -> Response:
        _, session = require_session(request)
        storage = resolved_container.artifact_storage
        if storage is None:
            return _error_response(
                request,
                status_code=503,
                code="ARTIFACT_STORAGE_UNAVAILABLE",
                message="artifact storage is unavailable",
            )
        try:
            key = ArtifactKey(
                owner_id=session.owner_id,
                namespace=ArtifactNamespace.EXPORT,
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                version=version,
            )
            stored = storage.read(key)
        except (ArtifactValidationError, ArtifactNotFound):
            return _error_response(
                request,
                status_code=404,
                code="ARTIFACT_NOT_FOUND",
                message="artifact is unavailable",
            )
        except ArtifactIntegrityError:
            return _error_response(
                request,
                status_code=409,
                code="ARTIFACT_INTEGRITY_FAILED",
                message="artifact integrity verification failed",
            )
        except ArtifactStorageError:
            return _error_response(
                request,
                status_code=503,
                code="ARTIFACT_STORAGE_UNAVAILABLE",
                message="artifact storage is unavailable",
            )
        return Response(
            content=stored.content,
            media_type=stored.manifest.media_type,
            headers={
                "Content-Disposition": _download_disposition(stored.manifest.file_name),
                "Content-Length": str(stored.manifest.size_bytes),
                "X-Artifact-SHA256": stored.manifest.sha256,
            },
        )

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
