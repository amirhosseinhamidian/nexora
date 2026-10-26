from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from nexora import __version__
from nexora.adapters.postgresql import RUNTIME_DATABASE_DSN_FILE_ENV, probe_database
from nexora.composition import ApplicationContainer, compose_application, compose_private_application
from nexora.config import RuntimeSettings, load_settings
from nexora.identity import SESSION_COOKIE_NAME, AuthenticationDenied, verify_exact_origin


class LivenessResponse(BaseModel):
    status: str
    service: str
    version: str


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
        title="Nexora API",
        version=__version__,
    )
    application.state.container = resolved_container

    @application.middleware("http")
    async def security_boundary(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if resolved_container.security is not None and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            try:
                verify_exact_origin(request.headers.get("origin"), resolved_container.security.canonical_origin)
            except AuthenticationDenied:
                return JSONResponse({"detail": "request denied"}, status_code=403)
            content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                return JSONResponse({"detail": "unsupported content type"}, status_code=415)
            session_token = request.cookies.get(SESSION_COOKIE_NAME)
            if session_token is not None:
                csrf_token = request.headers.get("x-csrf-token")
                repository = resolved_container.identity_repository
                if repository is None or csrf_token is None:
                    return JSONResponse({"detail": "request denied"}, status_code=403)
                try:
                    repository.authenticate_session(token=session_token, csrf_token=csrf_token)
                except AuthenticationDenied:
                    return JSONResponse({"detail": "request denied"}, status_code=403)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                too_large = int(content_length) > 1_048_576
            except ValueError:
                return JSONResponse({"detail": "invalid content length"}, status_code=400)
            if too_large:
                return JSONResponse({"detail": "request body too large"}, status_code=413)
        response = await call_next(request)
        nonce = secrets.token_urlsafe(18)
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

    @application.get("/health/live", response_model=LivenessResponse)
    def liveness() -> LivenessResponse:
        return LivenessResponse(status="ok", service="nexora-api", version=__version__)

    @application.get("/health/ready", include_in_schema=False)
    def readiness() -> Response:
        engine = resolved_container.database_engine
        if engine is None or resolved_container.security is None:
            return JSONResponse({"status": "not_configured"}, status_code=503)
        try:
            available = probe_database(engine)
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        if not available:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ready"})

    return application


app = create_app()


def run() -> None:
    if RUNTIME_DATABASE_DSN_FILE_ENV in os.environ:
        container = compose_private_application(environ=os.environ)
        settings = container.settings
        application = create_app(container=container)
    else:
        settings = load_settings()
        application = create_app(settings)
    uvicorn.run(
        application,
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
