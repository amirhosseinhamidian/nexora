from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from nexora import __version__
from nexora.config import CONFIG_SCHEMA_VERSION, RuntimeSettings, load_settings

SERVICE_NAME: Final = "nexora-api"


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    service: str
    version: str
    configuration_schema: str
    configuration_checksum: str


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    settings: RuntimeSettings
    identity: RuntimeIdentity


def compose_application(settings: RuntimeSettings | None = None) -> ApplicationContainer:
    resolved = load_settings() if settings is None else settings
    identity = RuntimeIdentity(
        service=SERVICE_NAME,
        version=__version__,
        configuration_schema=CONFIG_SCHEMA_VERSION,
        configuration_checksum=resolved.checksum(),
    )
    return ApplicationContainer(settings=resolved, identity=identity)
