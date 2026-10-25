from __future__ import annotations

import random
import re
import time
from collections.abc import Callable, Mapping
from typing import Any, Final, TypeVar
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ValidationError

from nexora.adapters.trd_bot.config import TrdBotSettings
from nexora.adapters.trd_bot.errors import (
    CapabilityNegotiationRequired,
    CursorExpiredError,
    IncompatibleProviderError,
    TrdBotResponseError,
    TrdBotSchemaError,
)
from nexora.adapters.trd_bot.models import (
    CapabilitiesResponse,
    CommandReceipt,
    DecisionReviewCommand,
    EventEnvelope,
    EventPage,
    ExportManifest,
    ExportRequest,
    ExportStatus,
    IntegrationErrorEnvelope,
    ResourceType,
    SnapshotPage,
)

API_NAMESPACE: Final = "/api/v1/integration/nexora"
CONTRACT_VERSION: Final = "nexora-trd-integration-v1"
REQUIRED_EVENT_ENVELOPE: Final = "trd-integration-event-envelope-v1"
REQUIRED_EXPORT_MANIFEST: Final = "nexora-export-manifest-v1"
REQUIRED_SOURCE_REFERENCE: Final = "nexora-source-reference-v1"
REQUIRED_COMMANDS: Final = frozenset(
    {
        "decision_review.accept.v1",
        "decision_review.reject.v1",
        "decision_review.defer.v1",
    }
)
RETRYABLE_STATUSES: Final = frozenset({429, 502, 503, 504})
MAXIMUM_ATTEMPTS: Final = 4
BASE_DELAY_SECONDS: Final = 0.250
MAXIMUM_DELAY_SECONDS: Final = 4.0
EVENT_ID_PATTERN: Final = re.compile(r"^evt_[A-Za-z0-9_-]{16,64}$")
EXPORT_ID_PATTERN: Final = re.compile(r"^exp_[A-Za-z0-9_-]{16,64}$")

ModelT = TypeVar("ModelT", bound=BaseModel)


def _provider_version(value: str) -> tuple[int, int, int]:
    try:
        parts = tuple(int(part) for part in value.split("."))
    except ValueError as error:
        raise IncompatibleProviderError("TRD Bot provider version is invalid") from error
    if len(parts) != 3:
        raise IncompatibleProviderError("TRD Bot provider version is invalid")
    return parts


class TrdBotClient:
    def __init__(
        self,
        settings: TrdBotSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self._settings = settings
        self._sleep = sleep
        self._jitter = jitter
        self._client = httpx.Client(
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            transport=transport,
            follow_redirects=False,
        )
        self._capabilities: CapabilitiesResponse | None = None

    def __enter__(self) -> TrdBotClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    @property
    def negotiated_provider_version(self) -> str | None:
        return None if self._capabilities is None else self._capabilities.provider_version

    def negotiate(self, *, correlation_id: UUID | None = None) -> CapabilitiesResponse:
        payload, response = self._request(
            "GET",
            f"{API_NAMESPACE}/capabilities",
            expected_status=200,
            correlation_id=correlation_id,
            requires_negotiation=False,
        )
        capabilities = self._parse(payload, CapabilitiesResponse)
        self._validate_capabilities(capabilities)
        self._validate_success_headers(response, expected_correlation_id=response.request.headers["X-Correlation-ID"])
        if response.headers["X-TRD-Bot-Version"] != capabilities.provider_version:
            raise TrdBotSchemaError("provider version header and capability payload disagree")
        self._capabilities = capabilities
        return capabilities

    def list_snapshots(
        self,
        resource_type: ResourceType,
        *,
        cursor: str | None = None,
        limit: int = 100,
        correlation_id: UUID | None = None,
    ) -> SnapshotPage:
        self._validate_limit(limit)
        params: dict[str, str | int] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        payload, _ = self._request(
            "GET",
            f"{API_NAMESPACE}/snapshots/{resource_type.value}",
            expected_status=200,
            params=params,
            correlation_id=correlation_id,
        )
        return self._parse(payload, SnapshotPage)

    def list_events(
        self,
        *,
        cursor: str | None = None,
        limit: int = 100,
        correlation_id: UUID | None = None,
    ) -> EventPage:
        self._validate_limit(limit)
        params: dict[str, str | int] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        payload, _ = self._request(
            "GET",
            f"{API_NAMESPACE}/events",
            expected_status=200,
            params=params,
            correlation_id=correlation_id,
        )
        return self._parse(payload, EventPage)

    def get_event(self, event_id: str, *, correlation_id: UUID | None = None) -> EventEnvelope:
        self._validate_identifier(event_id, EVENT_ID_PATTERN, "event")
        payload, _ = self._request(
            "GET",
            f"{API_NAMESPACE}/events/{quote(event_id, safe='')}",
            expected_status=200,
            correlation_id=correlation_id,
        )
        return self._parse(payload, EventEnvelope)

    def submit_decision_review(
        self,
        command: DecisionReviewCommand,
        *,
        idempotency_key: str,
        correlation_id: UUID | None = None,
    ) -> CommandReceipt:
        self._validate_idempotency_key(idempotency_key)
        payload, _ = self._request(
            "POST",
            f"{API_NAMESPACE}/commands/decision-reviews",
            expected_status=202,
            json=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        receipt = self._parse(payload, CommandReceipt)
        if receipt.idempotency_key != idempotency_key:
            raise TrdBotSchemaError("command receipt idempotency key mismatch")
        return receipt

    def create_export(
        self,
        request: ExportRequest,
        *,
        idempotency_key: str,
        correlation_id: UUID | None = None,
    ) -> ExportStatus:
        self._validate_idempotency_key(idempotency_key)
        payload, _ = self._request(
            "POST",
            f"{API_NAMESPACE}/exports",
            expected_status=202,
            json=request.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        return self._parse(payload, ExportStatus)

    def get_export(self, export_id: str, *, correlation_id: UUID | None = None) -> ExportStatus:
        self._validate_identifier(export_id, EXPORT_ID_PATTERN, "export")
        payload, _ = self._request(
            "GET",
            f"{API_NAMESPACE}/exports/{quote(export_id, safe='')}",
            expected_status=200,
            correlation_id=correlation_id,
        )
        return self._parse(payload, ExportStatus)

    def get_export_manifest(self, export_id: str, *, correlation_id: UUID | None = None) -> ExportManifest:
        self._validate_identifier(export_id, EXPORT_ID_PATTERN, "export")
        payload, _ = self._request(
            "GET",
            f"{API_NAMESPACE}/exports/{quote(export_id, safe='')}/manifest",
            expected_status=200,
            correlation_id=correlation_id,
        )
        return self._parse(payload, ExportManifest)

    def _request(
        self,
        method: str,
        path: str,
        *,
        expected_status: int,
        params: Mapping[str, str | int] | None = None,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        correlation_id: UUID | None = None,
        requires_negotiation: bool = True,
    ) -> tuple[Any, httpx.Response]:
        if requires_negotiation and self._capabilities is None:
            raise CapabilityNegotiationRequired("TRD Bot capabilities must be negotiated before synchronization")
        request_correlation_id = str(correlation_id or uuid4())
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._settings.token.get_secret_value()}",
            "X-Correlation-ID": request_correlation_id,
        }
        if method == "POST":
            if idempotency_key is None:
                raise ValueError("POST requests require an idempotency key")
            headers["Content-Type"] = "application/json"
            headers["Idempotency-Key"] = idempotency_key

        response: httpx.Response | None = None
        for attempt in range(1, MAXIMUM_ATTEMPTS + 1):
            response = self._client.request(method, path, params=params, json=json, headers=headers)
            if response.status_code not in RETRYABLE_STATUSES or attempt == MAXIMUM_ATTEMPTS:
                break
            self._sleep(self._retry_delay(response, attempt))
        assert response is not None
        if response.status_code >= 400:
            if response.status_code == 412:
                self._capabilities = None
            self._raise_response_error(response)
        if response.status_code != expected_status:
            raise TrdBotSchemaError(
                f"TRD Bot response status is invalid: expected={expected_status}, actual={response.status_code}"
            )
        self._validate_success_headers(response, expected_correlation_id=request_correlation_id)
        try:
            return response.json(), response
        except ValueError as error:
            raise TrdBotSchemaError("TRD Bot response is not valid JSON") from error

    def _validate_success_headers(self, response: httpx.Response, *, expected_correlation_id: str) -> None:
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise TrdBotSchemaError("TRD Bot response content type is invalid")
        if response.headers.get("X-Correlation-ID") != expected_correlation_id:
            raise TrdBotSchemaError("TRD Bot response correlation ID mismatch")
        if response.headers.get("X-Contract-Version") != CONTRACT_VERSION:
            raise TrdBotSchemaError("TRD Bot response contract version mismatch")
        provider = response.headers.get("X-TRD-Bot-Version")
        if provider is None:
            raise TrdBotSchemaError("TRD Bot response provider version is missing")
        if self._capabilities is not None and provider != self._capabilities.provider_version:
            self._capabilities = None
            raise IncompatibleProviderError("TRD Bot provider version changed after negotiation")

    def _validate_capabilities(self, capabilities: CapabilitiesResponse) -> None:
        version = _provider_version(capabilities.provider_version)
        if not ((0, 3, 1) <= version < (0, 4, 0)):
            raise IncompatibleProviderError("TRD Bot release is outside the accepted compatibility range")
        checks = (
            (set(capabilities.contract_versions), {CONTRACT_VERSION}, "contract versions"),
            (set(capabilities.event_envelopes), {REQUIRED_EVENT_ENVELOPE}, "event envelopes"),
            (set(capabilities.export_manifests), {REQUIRED_EXPORT_MANIFEST}, "export manifests"),
            (set(capabilities.source_references), {REQUIRED_SOURCE_REFERENCE}, "source references"),
            (set(capabilities.commands), set(REQUIRED_COMMANDS), "commands"),
        )
        for actual, expected, label in checks:
            if actual != expected:
                raise IncompatibleProviderError(f"TRD Bot {label} do not match the frozen compatibility matrix")

    def _raise_response_error(self, response: httpx.Response) -> None:
        try:
            envelope = IntegrationErrorEnvelope.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise TrdBotSchemaError(
                f"TRD Bot error response schema is invalid: status={response.status_code}"
            ) from error
        error_type = CursorExpiredError if response.status_code == 410 else TrdBotResponseError
        raise error_type(response.status_code, envelope.error.code, retryable=envelope.error.retryable)

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, min(float(retry_after), MAXIMUM_DELAY_SECONDS))
            except ValueError:
                pass
        ceiling = min(BASE_DELAY_SECONDS * (2 ** (attempt - 1)), MAXIMUM_DELAY_SECONDS)
        return self._jitter(0.0, ceiling)

    @staticmethod
    def _parse(payload: Any, model: type[ModelT]) -> ModelT:
        try:
            return model.model_validate(payload)
        except ValidationError as error:
            raise TrdBotSchemaError(f"TRD Bot response does not match {model.__name__}") from error

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if not 1 <= limit <= 500:
            raise ValueError("page limit must be between 1 and 500")

    @staticmethod
    def _validate_idempotency_key(value: str) -> None:
        if not 16 <= len(value) <= 160 or any(character.isspace() for character in value):
            raise ValueError("idempotency key must contain 16 to 160 non-whitespace characters")

    @staticmethod
    def _validate_identifier(value: str, pattern: re.Pattern[str], label: str) -> None:
        if pattern.fullmatch(value) is None:
            raise ValueError(f"{label} identifier is invalid")
