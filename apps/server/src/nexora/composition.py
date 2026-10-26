from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from sqlalchemy import Engine

from nexora import __version__
from nexora.adapters.postgresql import PostgreSQLIdentityRepository, create_database_engine, create_session_factory
from nexora.adapters.postgresql.config import (
    DATABASE_DSN_FILE_ENV,
    RUNTIME_DATABASE_DSN_FILE_ENV,
    load_database_settings,
)
from nexora.adapters.trd_bot import TrdBotClient, load_trd_bot_settings
from nexora.adapters.trd_bot.config import TRD_BOT_BASE_URL_FILE_ENV, TRD_BOT_TOKEN_FILE_ENV
from nexora.config import CONFIG_SCHEMA_VERSION, RuntimeSettings, load_settings
from nexora.identity import StandardWebAuthnVerifier, WebAuthnCeremonyVerifier
from nexora.identity_service import OwnerIdentityService
from nexora.security_config import (
    AUTH_PEPPER_FILE_ENV,
    CANONICAL_ORIGIN_FILE_ENV,
    SecuritySettings,
    load_security_settings,
)

SERVICE_NAME: Final = "nexora-api"
BUILD_COMMIT_SHA_ENV: Final = "SOURCE_COMMIT_SHA"


def _build_commit_sha(environ: Mapping[str, str]) -> str:
    value = environ.get(BUILD_COMMIT_SHA_ENV, "development")
    if value != "development" and re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError("build commit SHA is invalid")
    return value


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    service: str
    version: str
    commit_sha: str
    configuration_schema: str
    configuration_checksum: str


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    settings: RuntimeSettings
    identity: RuntimeIdentity
    database_engine: Engine | None = None
    identity_repository: PostgreSQLIdentityRepository | None = None
    security: SecuritySettings | None = None
    webauthn_verifier: WebAuthnCeremonyVerifier | None = None
    owner_identity_service: OwnerIdentityService | None = None
    trd_bot_client: TrdBotClient | None = None


def compose_application(settings: RuntimeSettings | None = None) -> ApplicationContainer:
    resolved = load_settings() if settings is None else settings
    identity = RuntimeIdentity(
        service=SERVICE_NAME,
        version=__version__,
        commit_sha="development",
        configuration_schema=CONFIG_SCHEMA_VERSION,
        configuration_checksum=resolved.checksum(),
    )
    return ApplicationContainer(settings=resolved, identity=identity)


PRIVATE_RUNTIME_ENVIRONMENT_VARIABLES: Final = frozenset(
    {
        DATABASE_DSN_FILE_ENV,
        RUNTIME_DATABASE_DSN_FILE_ENV,
        TRD_BOT_BASE_URL_FILE_ENV,
        TRD_BOT_TOKEN_FILE_ENV,
        CANONICAL_ORIGIN_FILE_ENV,
        AUTH_PEPPER_FILE_ENV,
    }
)


def compose_private_application(
    *,
    environ: Mapping[str, str],
    webauthn_verifier: WebAuthnCeremonyVerifier | None = None,
) -> ApplicationContainer:
    settings = load_settings(environ, permitted_external_variables=PRIVATE_RUNTIME_ENVIRONMENT_VARIABLES)
    database_settings = load_database_settings(environ, variable=RUNTIME_DATABASE_DSN_FILE_ENV)
    security = load_security_settings(environ)
    trd_bot_settings = load_trd_bot_settings(environ)
    engine = create_database_engine(database_settings)
    repository = PostgreSQLIdentityRepository(create_session_factory(engine))
    verifier = webauthn_verifier or StandardWebAuthnVerifier()
    identity = RuntimeIdentity(
        service=SERVICE_NAME,
        version=__version__,
        commit_sha=_build_commit_sha(environ),
        configuration_schema=CONFIG_SCHEMA_VERSION,
        configuration_checksum=settings.checksum(),
    )
    return ApplicationContainer(
        settings=settings,
        identity=identity,
        database_engine=engine,
        identity_repository=repository,
        security=security,
        webauthn_verifier=verifier,
        owner_identity_service=OwnerIdentityService(repository, verifier, security),
        trd_bot_client=TrdBotClient(trd_bot_settings),
    )
