from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import Mock
from uuid import UUID

import pytest
from nexora.adapters.postgresql.decision_projection import DecisionEventProjectionRepository
from nexora.adapters.postgresql.outcome_journal import OutcomeJournalEntryView, OutcomeJournalRepository
from nexora.outcome_journal import (
    CreateOutcomeJournalEntryRequest,
    OutcomeJournalEntryKind,
    OutcomeJournalService,
    OutcomeSourceKind,
    OutcomeSourceLineage,
    OutcomeUncertaintyLevel,
)
from pydantic import ValidationError


def _request(**changes: object) -> CreateOutcomeJournalEntryRequest:
    value: dict[str, object] = {
        "entry_kind": "owner_note",
        "content": "  Observe without rewriting evidence.  ",
        "uncertainty_level": "medium",
        "uncertainty_note": "  Regime confidence is incomplete. ",
        "occurred_at": datetime.now(UTC) - timedelta(minutes=1),
    }
    value.update(changes)
    return CreateOutcomeJournalEntryRequest.model_validate(value)


def _view(request: CreateOutcomeJournalEntryRequest) -> OutcomeJournalEntryView:
    now = datetime.now(UTC)
    return OutcomeJournalEntryView(
        entry_id=UUID("871b8a59-d278-4bce-a034-80b52f45ee03"),
        decision_id="decision-1",
        entry_kind=request.entry_kind.value,
        content=request.content,
        uncertainty_level=request.uncertainty_level.value,
        uncertainty_note=request.uncertainty_note,
        review_id=request.review_id,
        portfolio_id=request.portfolio_id,
        simulated_position_reference=request.simulated_position_reference,
        decision_evidence_generation=2,
        decision_evidence_checksum="sha256:" + "a" * 64,
        decision_source_reference={
            "schema_version": "nexora-source-reference-v1",
            "source_product": "trd_bot",
            "source_version": "0.3.1",
            "resource_type": "decision_evaluation",
            "resource_id": "decision-1",
            "resource_schema_version": "trd-decision-evaluation-v1",
            "observed_at": request.occurred_at.isoformat(),
            "checksum": "sha256:" + "a" * 64,
        },
        source_lineage=(None if request.source_lineage is None else request.source_lineage.model_dump(mode="json")),
        occurred_at=request.occurred_at,
        recorded_at=now,
        supersedes_entry_id=request.supersedes_entry_id,
        idempotency_key="outcome-journal-unit-key-0001",
    )


def test_request_normalizes_owner_text_and_requires_observed_outcome_lineage() -> None:
    request = _request()
    assert request.content == "Observe without rewriting evidence."
    assert request.uncertainty_note == "Regime confidence is incomplete."

    with pytest.raises(ValidationError, match="requires source lineage"):
        _request(entry_kind="observed_outcome")


def test_correction_requires_superseded_entry_and_rejects_mutation_capabilities() -> None:
    with pytest.raises(ValidationError, match="requires exactly one"):
        _request(entry_kind="correction")
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CreateOutcomeJournalEntryRequest.model_validate(
            {
                "entry_kind": "owner_note",
                "content": "Owner-authored note",
                "uncertainty_level": "low",
                "occurred_at": datetime.now(UTC) - timedelta(minutes=1),
                "ai_generated": True,
            }
        )


def test_observed_outcome_accepts_bounded_source_lineage() -> None:
    occurred_at = datetime.now(UTC) - timedelta(minutes=1)
    request = CreateOutcomeJournalEntryRequest(
        entry_kind=OutcomeJournalEntryKind.OBSERVED_OUTCOME,
        content="Paper position remained within the expected range.",
        uncertainty_level=OutcomeUncertaintyLevel.LOW,
        source_lineage=OutcomeSourceLineage(
            source_kind=OutcomeSourceKind.PORTFOLIO_SNAPSHOT,
            source_id="paper-snapshot-1",
            observed_at=occurred_at,
            checksum="sha256:" + "b" * 64,
        ),
        occurred_at=occurred_at,
    )
    assert request.source_lineage is not None
    assert request.source_lineage.source_kind is OutcomeSourceKind.PORTFOLIO_SNAPSHOT


def test_exact_replay_remains_owner_authored_append_only_and_non_executable() -> None:
    owner_id = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
    request = _request()
    repository_mock = Mock(spec=OutcomeJournalRepository)
    repository_mock.find_by_idempotency_key.return_value = _view(request)
    projections_mock = Mock(spec=DecisionEventProjectionRepository)
    service = OutcomeJournalService(
        cast(OutcomeJournalRepository, repository_mock),
        cast(DecisionEventProjectionRepository, projections_mock),
    )

    response = service.record(
        owner_id,
        "decision-1",
        request,
        idempotency_key="outcome-journal-unit-key-0001",
    )

    assert response.author_kind == "owner"
    assert response.append_only is True
    assert response.ai_generated is False
    assert response.provider_rewritable is False
    assert response.execution_authorization is False
    assert response.transaction_created is False
    assert response.order_intent_created is False
    projections_mock.active_snapshot.assert_not_called()
    repository_mock.record.assert_not_called()
