from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import cast

import pytest
from nexora.observability import (
    LOG_BACKUP_COUNT,
    LOG_ROTATION_BYTES,
    MAXIMUM_ROUTE_DIMENSIONS,
    ObservabilityConfigurationError,
    ObservabilitySettings,
    RuntimeMetrics,
    StructuredEventLogger,
    StructuredJsonFormatter,
    configure_structured_logging,
    create_runtime_observability,
    database_pool_values,
    load_observability_settings,
    redact_sensitive,
)
from nexora.security_audit import SecurityAuditMetadataError, sanitize_audit_metadata


def test_observability_settings_are_private_and_rotation_is_bounded(tmp_path: Path) -> None:
    path = tmp_path / "nexora.jsonl"
    settings = load_observability_settings({"NEXORA_LOG_FILE": str(path)}, production=True)
    assert settings.log_file == path
    assert settings.max_bytes == LOG_ROTATION_BYTES
    assert settings.backup_count == LOG_BACKUP_COUNT

    with pytest.raises(ObservabilityConfigurationError, match="production requires"):
        load_observability_settings({}, production=True)
    with pytest.raises(ObservabilityConfigurationError, match="absolute"):
        ObservabilitySettings(log_file=Path("relative.jsonl"))


def test_structured_formatter_redacts_nested_secrets_and_connection_credentials() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredJsonFormatter(service="nexora-test"))
    logger = logging.Logger("nexora-test")
    logger.addHandler(handler)
    events = StructuredEventLogger(logger)

    events.emit(
        logging.INFO,
        "security.redaction.checked",
        reason_code="REDACTION_CHECKED",
        fields={
            "authorization": "Bearer super-secret-token",
            "nested": {"recovery_code": "never-log-this"},
            "database": "postgresql://owner:database-password@postgres/nexora",
            "safe": "visible",
        },
    )

    output = stream.getvalue()
    payload = json.loads(output)
    assert "super-secret-token" not in output
    assert "never-log-this" not in output
    assert "database-password" not in output
    assert payload["fields"]["authorization"] == "[REDACTED]"
    assert payload["fields"]["safe"] == "visible"
    assert payload["schema_version"] == "nexora-observability-event-v1"


def test_free_text_redaction_covers_bearer_cookie_and_url_credentials() -> None:
    source = (
        "Bearer abcdefghijklmnop "
        "__Host-nexora_session=abcdefghijklmnop "
        "postgresql://owner:password-value@postgres/nexora"
    )
    redacted = redact_sensitive(source)
    assert isinstance(redacted, str)
    assert "abcdefghijklmnop" not in redacted
    assert "password-value" not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_metric_snapshot_has_bounded_request_job_and_pool_dimensions() -> None:
    metrics = RuntimeMetrics()
    metrics.observe_request(method="GET", route="/version", status_code=200, duration_ms=12.5)
    metrics.observe_request(method="POST", route="/v1/auth/logout", status_code=403, duration_ms=350.0)
    metrics.observe_job_cycle(claimed=3, succeeded=2, failed=1)
    metrics.update_database_pool({"size": 5, "checked_in": 3, "checked_out": 2, "overflow": 0})

    snapshot = metrics.snapshot()
    assert snapshot["schema_version"] == "nexora-runtime-metrics-v1"
    assert snapshot["requests"] == {
        "total": 2,
        "by_status_class": {"2xx": 1, "4xx": 1},
        "by_route": {"GET /version": 1, "POST /v1/auth/logout": 1},
        "duration_ms": {
            "count": 2,
            "sum": 362.5,
            "buckets": {"25": 1, "50": 1, "100": 1, "300": 1, "1000": 2, "5000": 2, "+Inf": 2},
        },
    }
    assert snapshot["jobs"] == {"cycles": 1, "claimed": 3, "succeeded": 2, "failed": 1}
    assert snapshot["database_pool"] == {
        "status": "ready",
        "size": 5,
        "checked_in": 3,
        "checked_out": 2,
        "overflow": 0,
    }


def test_invalid_job_metrics_are_rejected() -> None:
    with pytest.raises(ValueError, match="invalid"):
        RuntimeMetrics().observe_job_cycle(claimed=1, succeeded=1, failed=1)


def test_route_metric_cardinality_is_bounded() -> None:
    metrics = RuntimeMetrics()
    for index in range(MAXIMUM_ROUTE_DIMENSIONS + 10):
        metrics.observe_request(method="GET", route=f"/route-{index}", status_code=200, duration_ms=1)
    request_metrics = cast(dict[str, object], metrics.snapshot()["requests"])
    routes = cast(dict[str, int], request_metrics["by_route"])
    assert len(routes) == MAXIMUM_ROUTE_DIMENSIONS + 1
    assert routes["OTHER <overflow>"] == 10


def test_rotating_json_log_handler_writes_a_safe_event(tmp_path: Path) -> None:
    log_file = tmp_path / "nexora.jsonl"
    runtime = create_runtime_observability(
        service="nexora-test",
        settings=ObservabilitySettings(log_file=log_file, max_bytes=512, backup_count=2),
    )
    configure_structured_logging(runtime, level="INFO")
    runtime.events.emit(
        logging.INFO,
        "runtime.started",
        reason_code="RUNTIME_STARTED",
        fields={"configuration_checksum": "a" * 64},
    )
    for handler in runtime.events.logger.handlers:
        handler.flush()

    payload = json.loads(log_file.read_text(encoding="utf-8"))
    assert payload["service"] == "nexora-test"
    assert payload["event"] == "runtime.started"


def test_log_file_symlink_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.jsonl"
    target.touch()
    link = tmp_path / "link.jsonl"
    link.symlink_to(target)
    runtime = create_runtime_observability(
        service="nexora-test",
        settings=ObservabilitySettings(log_file=link),
    )
    with pytest.raises(ObservabilityConfigurationError, match="symbolic link"):
        configure_structured_logging(runtime, level="INFO")


def test_security_audit_metadata_rejects_secret_keys_and_unbounded_values() -> None:
    assert sanitize_audit_metadata({"credential_kind": "passkey", "user_verification": True}) == {
        "credential_kind": "passkey",
        "user_verification": True,
    }
    with pytest.raises(SecurityAuditMetadataError, match="secret-bearing"):
        sanitize_audit_metadata({"recovery_code": "must-not-persist"})
    with pytest.raises(SecurityAuditMetadataError, match="scalar"):
        sanitize_audit_metadata({"nested": {"unsafe": "value"}})


def test_database_pool_metrics_use_only_numeric_pool_state() -> None:
    class Pool:
        def size(self) -> int:
            return 5

        def checkedin(self) -> int:
            return 4

        def checkedout(self) -> int:
            return 1

        def overflow(self) -> int:
            return 0

    class Engine:
        pool = Pool()

    assert database_pool_values(Engine()) == {"size": 5, "checked_in": 4, "checked_out": 1, "overflow": 0}
