from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nexora.adapters.trd_bot.models import EventEnvelope, ResourceType, SourceReference
from nexora.decision_event_projection import (
    DecisionKind,
    canonical_json_sha256,
    project_event,
    project_snapshot,
    source_reference_checksum,
)

NOW = datetime(2026, 11, 12, 8, tzinfo=UTC)


def snapshot_item(
    resource_type: ResourceType = ResourceType.CANDIDATE,
    *,
    schema: str = "trd-bot-candidate-v1",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "resource_schema_version": schema,
        "candidate_id": "candidate-1",
        "offline_only": True,
        "external_order_submission_allowed": False,
    }
    reference = SourceReference(
        schema_version="nexora-source-reference-v1",
        source_product="trd_bot",
        source_version="0.3.1",
        resource_type=resource_type.value,
        resource_id="candidate-1",
        resource_schema_version=schema,
        observed_at=NOW,
        checksum="sha256:" + "0" * 64,
    )
    reference = reference.model_copy(
        update={"checksum": source_reference_checksum(reference, payload)}
    )
    return {"source_reference": reference.model_dump(mode="json"), "payload": payload}


def decision_event(*, version: int = 1, schema: str = "trd-bot-decision-evaluated-event-v1") -> EventEnvelope:
    payload = {
        "decision": "defer",
        "offline_only": True,
        "external_order_submission_allowed": False,
    }
    reference = SourceReference(
        schema_version="nexora-source-reference-v1",
        source_product="trd_bot",
        source_version="0.3.1",
        resource_type="decision_evaluation",
        resource_id="decision-1",
        resource_schema_version=schema,
        observed_at=NOW,
        checksum="sha256:" + "0" * 64,
    )
    reference = reference.model_copy(
        update={"checksum": source_reference_checksum(reference, payload)}
    )
    return EventEnvelope.model_validate(
        {
            "schema_version": "trd-integration-event-envelope-v1",
            "event_id": f"evt_decision_projection_{version:04d}",
            "event_type": "decision.evaluation.completed.v1",
            "occurred_at": NOW,
            "emitted_at": NOW,
            "source": reference.model_dump(mode="json"),
            "aggregate": {"type": "decision_evaluation", "id": "decision-1", "version": version},
            "correlation_id": "d7d23916-e3d5-41ee-932e-1f1ae08c1825",
            "causation_id": None,
            "idempotency_key": f"decision-projection-version-{version:04d}",
            "payload_schema": schema,
            "payload": payload,
            "payload_checksum": "sha256:" + canonical_json_sha256(payload),
        }
    )


def test_source_referenced_snapshot_projects_owner_review_pending_record() -> None:
    record = project_snapshot(ResourceType.CANDIDATE, snapshot_item(), provider_release="0.3.1")

    assert record.resource_id == "candidate-1"
    assert record.decision_kind is DecisionKind.CANDIDATE
    assert record.local_state.value == "review_pending"
    assert record.source_event_id is None


def test_snapshot_checksum_and_unknown_schema_fail_closed() -> None:
    tampered = snapshot_item()
    tampered["payload"] = {"resource_schema_version": "trd-bot-candidate-v1", "candidate_id": "changed"}
    with pytest.raises(ValueError, match="source-referenced"):
        project_snapshot(ResourceType.CANDIDATE, tampered, provider_release="0.3.1")

    with pytest.raises(ValueError, match="unsupported snapshot schema"):
        project_snapshot(
            ResourceType.CANDIDATE,
            snapshot_item(schema="future-candidate-v9"),
            provider_release="0.3.1",
        )


def test_real_v031_decision_event_schema_projects_aggregate_lineage() -> None:
    record = project_event(decision_event(version=2), provider_release="0.3.1")

    assert record is not None
    assert record.aggregate_type == "decision_evaluation"
    assert record.aggregate_id == "decision-1"
    assert record.aggregate_version == 2
    assert record.payload_sha256 == canonical_json_sha256(record.payload)


def test_event_source_checksum_and_unlisted_schema_fail_closed() -> None:
    changed = decision_event().model_dump(mode="json")
    changed["source"]["checksum"] = "sha256:" + "f" * 64
    forged = EventEnvelope.model_validate(changed)
    with pytest.raises(ValueError, match="source reference checksum"):
        project_event(forged, provider_release="0.3.1")

    with pytest.raises(ValueError, match="unsupported decision event"):
        project_event(decision_event(schema="future-decision-v9"), provider_release="0.3.1")
