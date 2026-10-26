from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RUNTIME_API_SCHEMA_VERSION = "nexora-runtime-api-v1"
ERROR_ENVELOPE_SCHEMA_VERSION = "nexora-error-envelope-v1"


def _webauthn_algorithms() -> list[Literal["ES256", "EdDSA"]]:
    return ["ES256", "EdDSA"]


class RuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorDetail(RuntimeModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,79}$")
    message: str = Field(min_length=1, max_length=240)


class ErrorEnvelope(RuntimeModel):
    schema_version: Literal["nexora-error-envelope-v1"] = "nexora-error-envelope-v1"
    correlation_id: UUID
    error: ErrorDetail


class ActionRequest(RuntimeModel):
    pass


class VersionResponse(RuntimeModel):
    schema_version: Literal["nexora-runtime-api-v1"] = "nexora-runtime-api-v1"
    service: Literal["nexora-api"]
    version: str
    commit_sha: str
    configuration_schema: str
    configuration_checksum: str


class BootstrapOptionsRequest(RuntimeModel):
    bootstrap_token: str = Field(min_length=32, max_length=256)


class BootstrapCompleteRequest(RuntimeModel):
    bootstrap_token: str = Field(min_length=32, max_length=256)
    response_json: str = Field(min_length=2, max_length=131_072)


class AuthenticationCompleteRequest(RuntimeModel):
    credential_id: str = Field(min_length=16, max_length=1024)
    challenge: str = Field(min_length=32, max_length=256)
    response_json: str = Field(min_length=2, max_length=131_072)


class RegistrationCompleteRequest(RuntimeModel):
    challenge: str = Field(min_length=32, max_length=256)
    response_json: str = Field(min_length=2, max_length=131_072)


class RecoveryOptionsRequest(RuntimeModel):
    recovery_code: str = Field(min_length=16, max_length=256)


class RecoveryCompleteRequest(RuntimeModel):
    owner_id: UUID
    challenge: str = Field(min_length=32, max_length=256)
    response_json: str = Field(min_length=2, max_length=131_072)


class AuthenticatorDescriptor(RuntimeModel):
    credential_id: str
    transports: list[str]


class AuthenticationOptionsResponse(RuntimeModel):
    schema_version: Literal["nexora-runtime-api-v1"] = "nexora-runtime-api-v1"
    challenge: str
    rp_id: str
    timeout_ms: Literal[300000] = 300000
    user_verification: Literal["required"] = "required"
    allow_credentials: list[AuthenticatorDescriptor]


class RegistrationOptionsResponse(RuntimeModel):
    schema_version: Literal["nexora-runtime-api-v1"] = "nexora-runtime-api-v1"
    owner_id: UUID | None = None
    challenge: str
    rp_id: str
    rp_name: Literal["Nexora"] = "Nexora"
    user_name: Literal["primary_owner"] = "primary_owner"
    timeout_ms: Literal[300000] = 300000
    user_verification: Literal["required"] = "required"
    resident_key: Literal["required"] = "required"
    algorithms: list[Literal["ES256", "EdDSA"]] = Field(default_factory=_webauthn_algorithms)


class BootstrapCompleteResponse(RuntimeModel):
    schema_version: Literal["nexora-runtime-api-v1"] = "nexora-runtime-api-v1"
    owner_id: UUID
    recovery_codes: list[str]


class SessionResponse(RuntimeModel):
    schema_version: Literal["nexora-runtime-api-v1"] = "nexora-runtime-api-v1"
    owner_id: UUID
    csrf_token: str | None = None
    idle_expires_at: datetime | None = None
    absolute_expires_at: datetime | None = None
    rotation_required: bool
    recently_reauthenticated: bool


class ActionResponse(RuntimeModel):
    schema_version: Literal["nexora-runtime-api-v1"] = "nexora-runtime-api-v1"
    status: Literal["accepted", "completed"]


GENERATED_MODEL_TYPES: tuple[type[RuntimeModel], ...] = (
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
