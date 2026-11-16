from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import Mock
from uuid import UUID

import pytest
from nexora.adapters.postgresql.decision_projection import (
    ActiveDecisionProjection,
    DecisionEventProjectionRepository,
)
from nexora.adapters.postgresql.decision_review import DecisionReviewRepository, DecisionReviewView
from nexora.adapters.trd_bot import ResourceType, TrdBotIntegrationMode
from nexora.decision_event_projection import (
    DecisionKind,
    DecisionProjectionRecord,
    canonical_json_sha256,
)
from nexora.decision_review import CreateDecisionReviewRequest, DecisionReviewService
from pydantic import ValidationError


def _request(**changes: object) -> dict[str, object]:
    reviewed_at = datetime.now(UTC) - timedelta(minutes=1)
    value: dict[str, object] = {
        "action": "accept",
        "portfolio_mode": "paper",
        "reason_code": "owner.accept.evidence_sufficient",
        "reason_note": None,
        "reviewed_at": reviewed_at,
        "revisit_at": None,
        "expected_version": 0,
        "evidence_generation": 7,
        "source_evidence_checksum": "sha256:" + "a" * 64,
        "supersedes_review_id": None,
    }
    value.update(changes)
    return value


def test_owner_review_accepts_only_a_reason_from_the_selected_action_namespace() -> None:
    with pytest.raises(ValidationError, match="selected owner action"):
        CreateDecisionReviewRequest.model_validate(_request(reason_code="owner.reject.low_confidence"))


def test_other_reason_requires_a_non_blank_owner_note() -> None:
    with pytest.raises(ValidationError, match="requires a reason note"):
        CreateDecisionReviewRequest.model_validate(_request(reason_code="owner.accept.other_with_note"))


def test_only_defer_may_have_a_future_revisit_time() -> None:
    reviewed_at = datetime.now(UTC) - timedelta(minutes=2)
    with pytest.raises(ValidationError, match="only a deferred review"):
        CreateDecisionReviewRequest.model_validate(
            _request(reviewed_at=reviewed_at, revisit_at=reviewed_at + timedelta(days=1))
        )
    deferred = CreateDecisionReviewRequest.model_validate(
        _request(
            action="defer",
            reason_code="owner.defer.review_later",
            reviewed_at=reviewed_at,
            revisit_at=reviewed_at + timedelta(days=1),
        )
    )
    assert deferred.action == "defer"


def test_live_execution_fields_are_rejected_as_unknown_input() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CreateDecisionReviewRequest.model_validate(_request(execute_order=True))


def test_service_binds_review_to_exact_active_evidence_without_execution_side_effects() -> None:
    owner_id = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
    decision_id = "decision-review-service"
    reviewed_at = datetime.now(UTC) - timedelta(minutes=1)
    payload = {
        "resource_schema_version": "trd-bot-decision-evaluation-v1",
        "decision_evaluation_id": decision_id,
        "offline_only": True,
        "external_order_submission_allowed": False,
    }
    record = DecisionProjectionRecord(
        resource_type=ResourceType.DECISION_EVALUATION,
        resource_id=decision_id,
        decision_kind=DecisionKind.PORTFOLIO_ASSESSMENT,
        provider_release="0.3.1",
        source_schema_version="trd-bot-decision-evaluation-v1",
        source_observed_at=reviewed_at,
        source_checksum="sha256:" + "a" * 64,
        payload=payload,
        payload_sha256=canonical_json_sha256(payload),
    )
    projection_mock = Mock(spec=DecisionEventProjectionRepository)
    projection_mock.active_snapshot.return_value = ActiveDecisionProjection(
        generation=7,
        trigger="cursor_expired",
        provider_version="0.3.1",
        contract_version="nexora-trd-integration-v1",
        projection={f"decision_evaluation:{decision_id}": record.model_dump(mode="json")},
    )
    repository_mock = Mock(spec=DecisionReviewRepository)
    repository_mock.find_by_idempotency_key.return_value = None
    repository_mock.record.return_value = (
        DecisionReviewView(
            review_id=UUID("9fd488e8-6e79-4cf6-b00d-6a3f1f8d8f47"),
            decision_id=decision_id,
            review_version=1,
            action="accept",
            portfolio_mode="paper",
            reason_code="owner.accept.evidence_sufficient",
            reason_note=None,
            evidence_generation=7,
            source_evidence_checksum=record.source_checksum,
            source_reference={
                "schema_version": "nexora-source-reference-v1",
                "source_product": "trd_bot",
                "source_version": "0.3.1",
                "resource_type": "decision_evaluation",
                "resource_id": decision_id,
                "resource_schema_version": "trd-bot-decision-evaluation-v1",
                "observed_at": reviewed_at.isoformat(),
                "checksum": record.source_checksum,
            },
            reviewed_at=reviewed_at,
            recorded_at=datetime.now(UTC),
            revisit_at=None,
            supersedes_review_id=None,
            delivery_status="pending",
            provider_command_id=None,
            provider_accepted_at=None,
            delivery_attempt_count=0,
        ),
        False,
    )
    service = DecisionReviewService(
        cast(DecisionReviewRepository, repository_mock),
        cast(DecisionEventProjectionRepository, projection_mock),
        None,
        TrdBotIntegrationMode.DISABLED_INCOMPATIBLE_PROVIDER,
    )
    response = service.record(
        owner_id,
        decision_id,
        CreateDecisionReviewRequest.model_validate(_request(reviewed_at=reviewed_at)),
        idempotency_key="decision-review-service-idempotency-key",
        correlation_id=UUID("5cb3e48e-a05e-44e4-b505-84385073deec"),
    )
    write = repository_mock.record.call_args.args[1]
    assert write.evidence_generation == 7
    assert write.source_evidence_checksum == record.source_checksum
    assert response.local_state == "accepted"
    assert response.execution_authorization is False
    assert response.order_intent_created is False
    assert response.transaction_created is False
