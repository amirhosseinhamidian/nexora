from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from nexora import __version__
from nexora.composition import compose_application
from nexora.config import RuntimeSettings, load_settings


class LivenessResponse(BaseModel):
    status: str
    service: str
    version: str


def create_app(settings: RuntimeSettings | None = None) -> FastAPI:
    container = compose_application(settings)
    application = FastAPI(
        docs_url=None,
        redoc_url=None,
        title="Nexora API",
        version=__version__,
    )
    application.state.container = container

    @application.get("/health/live", response_model=LivenessResponse)
    def liveness() -> LivenessResponse:
        return LivenessResponse(status="ok", service="nexora-api", version=__version__)

    return application


app = create_app()


def run() -> None:
    settings = load_settings()
    uvicorn.run(
        create_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
