from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

CONFIG_SCHEMA_VERSION = "nexora-runtime-configuration-v1"
ENV_PREFIX = "NEXORA_"
FORBIDDEN_DEPLOYMENT_PROFILE = "public_internet"


class ConfigurationError(ValueError):
    """Raised when runtime configuration cannot be accepted safely."""


class RuntimeEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class DeploymentProfile(StrEnum):
    LOCAL_DEVELOPMENT = "local_development"
    PRIVATE_SINGLE_HOST = "private_single_host"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Locale(StrEnum):
    PERSIAN = "fa"
    ENGLISH = "en"


class Theme(StrEnum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: RuntimeEnvironment = RuntimeEnvironment.DEVELOPMENT
    deployment_profile: DeploymentProfile = DeploymentProfile.LOCAL_DEVELOPMENT
    log_level: LogLevel = LogLevel.INFO
    default_locale: Locale = Locale.PERSIAN
    default_theme: Theme = Theme.SYSTEM
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1024, le=65535)

    @model_validator(mode="after")
    def validate_profile_boundary(self) -> RuntimeSettings:
        if self.environment is RuntimeEnvironment.PRODUCTION:
            if self.deployment_profile is not DeploymentProfile.PRIVATE_SINGLE_HOST:
                raise ValueError("production requires the private_single_host deployment profile")
            if self.log_level is LogLevel.DEBUG:
                raise ValueError("production forbids DEBUG logging")
        elif self.deployment_profile is not DeploymentProfile.LOCAL_DEVELOPMENT:
            raise ValueError("non-production environments require the local_development profile")

        if self.deployment_profile is DeploymentProfile.LOCAL_DEVELOPMENT and self.api_host != "127.0.0.1":
            raise ValueError("local_development must bind the API to 127.0.0.1")
        if self.deployment_profile is DeploymentProfile.PRIVATE_SINGLE_HOST and self.api_host not in {
            "0.0.0.0",
            "127.0.0.1",
        }:
            raise ValueError("private_single_host API host must remain inside the declared topology")
        return self

    @property
    def debug(self) -> bool:
        return self.environment is RuntimeEnvironment.DEVELOPMENT

    def checksum(self) -> str:
        payload = {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "settings": self.model_dump(mode="json"),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


ENVIRONMENT_VARIABLES = {
    "NEXORA_ENVIRONMENT": "environment",
    "NEXORA_DEPLOYMENT_PROFILE": "deployment_profile",
    "NEXORA_LOG_LEVEL": "log_level",
    "NEXORA_DEFAULT_LOCALE": "default_locale",
    "NEXORA_DEFAULT_THEME": "default_theme",
    "NEXORA_API_HOST": "api_host",
    "NEXORA_API_PORT": "api_port",
}


def _validation_error(error: ValidationError) -> ConfigurationError:
    details = []
    for item in error.errors():
        field = ".".join(str(part) for part in item["loc"]) or "settings"
        details.append(f"{field}: {item['msg']}")
    return ConfigurationError(f"invalid runtime configuration: {'; '.join(sorted(details))}")


def load_settings(environ: Mapping[str, str] | None = None) -> RuntimeSettings:
    source = os.environ if environ is None else environ
    scoped = {key: value for key, value in source.items() if key.startswith(ENV_PREFIX)}
    unknown = sorted(set(scoped) - set(ENVIRONMENT_VARIABLES))
    if unknown:
        raise ConfigurationError(f"unknown Nexora environment variables: {', '.join(unknown)}")

    values: dict[str, object] = {}
    for variable, field in ENVIRONMENT_VARIABLES.items():
        if variable not in scoped:
            continue
        raw = scoped[variable]
        if not raw.strip():
            raise ConfigurationError(f"empty Nexora environment variable: {variable}")
        if field == "api_port":
            try:
                values[field] = int(raw)
            except ValueError as error:
                raise ConfigurationError("invalid runtime configuration fields: api_port") from error
        else:
            values[field] = raw

    try:
        return RuntimeSettings.model_validate(values)
    except ValidationError as error:
        raise _validation_error(error) from error
