from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from nexora import __version__


class LivenessResponse(BaseModel):
    status: str
    service: str
    version: str


def create_app() -> FastAPI:
    application = FastAPI(
        docs_url=None,
        redoc_url=None,
        title="Nexora API",
        version=__version__,
    )

    @application.get("/health/live", response_model=LivenessResponse)
    def liveness() -> LivenessResponse:
        return LivenessResponse(status="ok", service="nexora-api", version=__version__)

    return application


app = create_app()


def run() -> None:
    uvicorn.run("nexora.api:app", host="127.0.0.1", port=8000, reload=False)
