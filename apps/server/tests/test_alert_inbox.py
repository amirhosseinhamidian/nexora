from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import Mock
from uuid import UUID

import pytest
from nexora.adapters.postgresql.alert_inbox import AlertInboxRepository, AlertStateView
from nexora.adapters.postgresql.decision_projection import (
    ActiveDecisionProjection,
    DecisionEventProjectionRepository,
)
from nexora.adapters.trd_bot import ResourceType, TrdBotIntegrationMode
from nexora.alert_inbox import AlertInboxService, CreateAlertTransitionRequest
from nexora.decision_event_projection import DecisionKind, DecisionProjectionRecord, canonical_json_sha256
from pydantic import ValidationError


def _request(**changes: object) -> dict[str, object]:
    occurred_at = datetime.now(UTC) - timedelta(minutes=1)
    value: dict[str, object] = {
        "action": "acknowledge",
        "occurred_at": occurred_at,
        "snooze_until": None,
        "expected_version": 0,
        "evidence_generation": 3,
        "source_evidence_checksum": "sha256:" + "b" * 64,
    }
    value.update(changes)
    return value


def _record() -> DecisionProjectionRecord:
    observed_at = datetime.now(UTC) - timedelta(minutes=2)
    payload = {
        "resource_schema_version": "trd-bot-alert-v1",
        "alert_id": "alert-service-1",
        "severity": "warning",
        "message": "Candidate evidence requires owner attention.",
        "state": "open",
    }
    return DecisionProjectionRecord(
        resource_type=ResourceType.ALERT,
        resource_id="alert-service-1",
        decision_kind=DecisionKind.MONITORING_ALERT,
        provider_release="0.3.1",
        source_schema_version="trd-bot-alert-v1",
        source_observed_at=observed_at,
        source_checksum="sha256:" + "b" * 64,
        payload=payload,
        payload_sha256=canonical_json_sha256(payload),
    )


def test_snooze_requires_a_future_resume_time() -> None:
    with pytest.raises(ValidationError, match="snooze requires"):
        CreateAlertTransitionRequest.model_validate(_request(action="snooze"))
    with pytest.raises(ValidationError, match="must be in the future"):
        CreateAlertTransitionRequest.model_validate(
            _request(action="snooze", snooze_until=datetime.now(UTC) - timedelta(seconds=1))
        )


def test_acknowledgement_rejects_snooze_time_and_unknown_execution_input() -> None:
    with pytest.raises(ValidationError, match="only snooze"):
        CreateAlertTransitionRequest.model_validate(_request(snooze_until=datetime.now(UTC) + timedelta(hours=1)))
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CreateAlertTransitionRequest.model_validate(_request(execute_order=True))


def test_service_lists_source_alert_and_records_exact_owner_acknowledgement() -> None:
    owner_id = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
    record = _record()
    projection_mock = Mock(spec=DecisionEventProjectionRepository)
    projection_mock.active_snapshot.return_value = ActiveDecisionProjection(
        generation=3,
        trigger="event_page_complete",
        provider_version="0.3.1",
        contract_version="nexora-trd-integration-v1",
        projection={"alert:alert-service-1": record.model_dump(mode="json")},
    )
    repository_mock = Mock(spec=AlertInboxRepository)
    repository_mock.latest_for_alerts.return_value = {}
    repository_mock.list_for_alert.return_value = ()
    repository_mock.find_by_idempotency_key.return_value = None
    occurred_at = datetime.now(UTC) - timedelta(minutes=1)
    repository_mock.record.return_value = (
        AlertStateView(
            alert_history_id=UUID("0e8e786b-2764-4a98-8502-e610857d953e"),
            alert_id=record.resource_id,
            state_version=1,
            state="acknowledged",
            reason_code="owner.alert.acknowledged",
            snooze_until=None,
            evidence_generation=3,
            source_evidence_checksum=record.source_checksum,
            source_reference={},
            occurred_at=occurred_at,
            recorded_at=datetime.now(UTC),
        ),
        False,
    )
    service = AlertInboxService(
        cast(AlertInboxRepository, repository_mock),
        cast(DecisionEventProjectionRepository, projection_mock),
        TrdBotIntegrationMode.DISABLED_INCOMPATIBLE_PROVIDER,
    )

    inbox = service.list_inbox(owner_id, limit=50)
    assert len(inbox.items) == 1
    assert inbox.items[0].local_state == "open"
    assert inbox.items[0].source.checksum == record.source_checksum
    assert inbox.notification_delivery_enabled is False

    response = service.transition(
        owner_id,
        record.resource_id,
        CreateAlertTransitionRequest.model_validate(_request(occurred_at=occurred_at)),
        idempotency_key="alert-service-idempotency-key-0001",
    )
    write = repository_mock.record.call_args.args[1]
    assert write.state == "acknowledged"
    assert write.evidence_generation == 3
    assert write.source_evidence_checksum == record.source_checksum
    assert response.state == "acknowledged"
