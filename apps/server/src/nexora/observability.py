from __future__ import annotations

import json
import logging
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

OBSERVABILITY_EVENT_SCHEMA: Final = "nexora-observability-event-v1"
METRICS_SCHEMA: Final = "nexora-runtime-metrics-v1"
READINESS_SCHEMA: Final = "nexora-readiness-v1"
LOG_FILE_ENV: Final = "NEXORA_LOG_FILE"
LOG_ROTATION_BYTES: Final = 10 * 1024 * 1024
LOG_BACKUP_COUNT: Final = 30
REQUEST_DURATION_BUCKETS_MS: Final = (25, 50, 100, 300, 1_000, 5_000)
MAXIMUM_ROUTE_DIMENSIONS: Final = 64
_EVENT_PATTERN = re.compile(r"^[a-z][a-z0-9_.]{2,79}$")
_REASON_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,79}$")
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
_URL_CREDENTIAL_PATTERN = re.compile(r"(://[^:/\s]+:)[^@/\s]+(@)")
_COOKIE_PATTERN = re.compile(r"(?i)(__Host-nexora_session|session|csrf)[=:\s]+[^\s;,]{8,}")
_SENSITIVE_KEY_PARTS: Final = (
    "authorization",
    "cookie",
    "credential",
    "csrf",
    "password",
    "private_key",
    "recovery",
    "secret",
    "session",
    "token",
)


class ObservabilityConfigurationError(ValueError):
    """Raised when observability configuration would weaken the private boundary."""


class DependencyReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ready", "not_configured", "unavailable"]
    reason_code: str


class ReadinessSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["nexora-readiness-v1"] = READINESS_SCHEMA
    status: Literal["ready", "not_configured", "unavailable"]
    dependencies: dict[str, DependencyReadiness]


@dataclass(frozen=True, slots=True)
class ObservabilitySettings:
    log_file: Path | None
    max_bytes: int = LOG_ROTATION_BYTES
    backup_count: int = LOG_BACKUP_COUNT

    def __post_init__(self) -> None:
        if self.log_file is not None and not self.log_file.is_absolute():
            raise ObservabilityConfigurationError("log file path must be absolute")
        if self.max_bytes < 1 or self.backup_count < 1:
            raise ObservabilityConfigurationError("log rotation settings must be positive")


def load_observability_settings(
    environ: Mapping[str, str],
    *,
    production: bool,
) -> ObservabilitySettings:
    raw = environ.get(LOG_FILE_ENV)
    if raw is None:
        if production:
            raise ObservabilityConfigurationError("production requires NEXORA_LOG_FILE")
        return ObservabilitySettings(log_file=None)
    if not raw.strip():
        raise ObservabilityConfigurationError("NEXORA_LOG_FILE cannot be empty")
    return ObservabilitySettings(log_file=Path(raw))


def _redact_text(value: str) -> str:
    redacted = _BEARER_PATTERN.sub("Bearer [REDACTED]", value)
    redacted = _URL_CREDENTIAL_PATTERN.sub(r"\1[REDACTED]\2", redacted)
    return _COOKIE_PATTERN.sub(r"\1=[REDACTED]", redacted)


def redact_sensitive(value: object, *, key: str | None = None) -> object:
    normalized_key = "" if key is None else key.lower().replace("-", "_")
    if normalized_key and any(part in normalized_key for part in _SENSITIVE_KEY_PARTS):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(item_key): redact_sensitive(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


class StructuredJsonFormatter(logging.Formatter):
    """Formats only controlled structured fields; raw exception messages are never emitted."""

    def __init__(self, *, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "schema_version": OBSERVABILITY_EVENT_SCHEMA,
            "occurred_at": datetime.fromtimestamp(record.created, UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": self._service,
        }
        event = getattr(record, "nexora_event", None)
        if isinstance(event, Mapping):
            payload.update({str(key): redact_sensitive(value, key=str(key)) for key, value in event.items()})
        else:
            payload.update({"event": "logging.unstructured_rejected", "reason_code": "UNSTRUCTURED_LOG_REJECTED"})
        if record.exc_info is not None and record.exc_info[0] is not None:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class StructuredEventLogger:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def emit(
        self,
        level: int,
        event: str,
        *,
        reason_code: str,
        fields: Mapping[str, object] | None = None,
    ) -> None:
        if _EVENT_PATTERN.fullmatch(event) is None:
            raise ValueError("structured event name is invalid")
        if _REASON_PATTERN.fullmatch(reason_code) is None:
            raise ValueError("structured reason code is invalid")
        structured: dict[str, object] = {"event": event, "reason_code": reason_code}
        if fields:
            structured["fields"] = redact_sensitive(fields)
        self._logger.log(level, event, extra={"nexora_event": structured})


class RuntimeMetrics:
    """A bounded, in-process metric source for the single-host v0.1 runtime."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._request_total = 0
        self._request_status: dict[str, int] = {}
        self._request_routes: dict[str, int] = {}
        self._duration_count = 0
        self._duration_sum_ms = 0.0
        self._duration_buckets = {str(boundary): 0 for boundary in REQUEST_DURATION_BUCKETS_MS}
        self._duration_buckets["+Inf"] = 0
        self._job_cycles = 0
        self._jobs_claimed = 0
        self._jobs_succeeded = 0
        self._jobs_failed = 0
        self._database_pool: dict[str, int | str] = {"status": "not_configured"}

    def observe_request(self, *, method: str, route: str, status_code: int, duration_ms: float) -> None:
        normalized_method = method if method in {"GET", "POST", "PUT", "PATCH", "DELETE"} else "OTHER"
        normalized_route = route if route.startswith("/") and len(route) <= 160 else "<unmatched>"
        status_class = f"{status_code // 100}xx" if 100 <= status_code <= 599 else "invalid"
        observed_duration = max(0.0, duration_ms)
        with self._lock:
            self._request_total += 1
            self._request_status[status_class] = self._request_status.get(status_class, 0) + 1
            route_key = f"{normalized_method} {normalized_route}"
            if route_key not in self._request_routes and len(self._request_routes) >= MAXIMUM_ROUTE_DIMENSIONS:
                route_key = "OTHER <overflow>"
            self._request_routes[route_key] = self._request_routes.get(route_key, 0) + 1
            self._duration_count += 1
            self._duration_sum_ms += observed_duration
            for boundary in REQUEST_DURATION_BUCKETS_MS:
                if observed_duration <= boundary:
                    self._duration_buckets[str(boundary)] += 1
            self._duration_buckets["+Inf"] += 1

    def observe_job_cycle(self, *, claimed: int, succeeded: int, failed: int) -> None:
        if min(claimed, succeeded, failed) < 0 or succeeded + failed > claimed:
            raise ValueError("job metric values are invalid")
        with self._lock:
            self._job_cycles += 1
            self._jobs_claimed += claimed
            self._jobs_succeeded += succeeded
            self._jobs_failed += failed

    def update_database_pool(self, values: Mapping[str, int] | None) -> None:
        with self._lock:
            if values is None:
                self._database_pool = {"status": "not_configured"}
                return
            self._database_pool = {
                "status": "ready",
                "size": max(0, values.get("size", 0)),
                "checked_in": max(0, values.get("checked_in", 0)),
                "checked_out": max(0, values.get("checked_out", 0)),
                "overflow": max(0, values.get("overflow", 0)),
            }

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "schema_version": METRICS_SCHEMA,
                "requests": {
                    "total": self._request_total,
                    "by_status_class": dict(sorted(self._request_status.items())),
                    "by_route": dict(sorted(self._request_routes.items())),
                    "duration_ms": {
                        "count": self._duration_count,
                        "sum": round(self._duration_sum_ms, 3),
                        "buckets": dict(self._duration_buckets),
                    },
                },
                "jobs": {
                    "cycles": self._job_cycles,
                    "claimed": self._jobs_claimed,
                    "succeeded": self._jobs_succeeded,
                    "failed": self._jobs_failed,
                },
                "database_pool": dict(self._database_pool),
            }


@dataclass(frozen=True, slots=True)
class RuntimeObservability:
    events: StructuredEventLogger
    metrics: RuntimeMetrics
    settings: ObservabilitySettings

    def observe_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
        correlation_id: str,
        reason_code: str,
    ) -> None:
        self.metrics.observe_request(
            method=method,
            route=route,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        self.events.emit(
            logging.INFO if status_code < 500 else logging.ERROR,
            "http.request.completed",
            reason_code=reason_code,
            fields={
                "method": method,
                "route": route,
                "status_code": status_code,
                "duration_ms": round(max(0.0, duration_ms), 3),
                "correlation_id": correlation_id,
            },
        )

    def observe_job_cycle(self, *, claimed: int, succeeded: int, failed: int) -> None:
        self.metrics.observe_job_cycle(claimed=claimed, succeeded=succeeded, failed=failed)
        self.events.emit(
            logging.INFO if failed == 0 else logging.WARNING,
            "worker.cycle.completed",
            reason_code="WORKER_CYCLE_COMPLETED" if failed == 0 else "WORKER_CYCLE_PARTIAL_FAILURE",
            fields={"claimed": claimed, "succeeded": succeeded, "failed": failed},
        )


def create_runtime_observability(
    *,
    service: str,
    settings: ObservabilitySettings | None = None,
) -> RuntimeObservability:
    resolved = settings or ObservabilitySettings(log_file=None)
    logger = logging.getLogger(f"nexora.structured.{service}")
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return RuntimeObservability(StructuredEventLogger(logger), RuntimeMetrics(), resolved)


def configure_structured_logging(runtime: RuntimeObservability, *, level: str) -> None:
    logger = runtime.events.logger
    formatter = StructuredJsonFormatter(service=logger.name.removeprefix("nexora.structured."))
    settings = runtime.settings
    if settings.log_file is None:
        handler: logging.Handler = logging.StreamHandler()
    else:
        path = settings.log_file
        parent = path.parent
        if not parent.is_dir():
            raise ObservabilityConfigurationError("log file parent directory is unavailable")
        if path.exists() and stat.S_ISLNK(path.lstat().st_mode):
            raise ObservabilityConfigurationError("log file cannot be a symbolic link")
        handler = RotatingFileHandler(
            path,
            maxBytes=settings.max_bytes,
            backupCount=settings.backup_count,
            encoding="utf-8",
        )
    handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


def database_pool_values(engine: object) -> dict[str, int]:
    pool = getattr(engine, "pool", None)
    if pool is None:
        raise ValueError("database engine does not expose a pool")
    accessors = {
        "size": "size",
        "checked_in": "checkedin",
        "checked_out": "checkedout",
        "overflow": "overflow",
    }
    values: dict[str, int] = {}
    for output_name, accessor_name in accessors.items():
        accessor = getattr(pool, accessor_name, None)
        if not callable(accessor):
            raise ValueError("database pool metric is unavailable")
        values[output_name] = int(accessor())
    return values
