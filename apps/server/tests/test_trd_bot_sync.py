from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from nexora.adapters.postgresql import JobClaim
from nexora.adapters.trd_bot import CursorExpiredError, EventPage, ResourceType, SnapshotPage
from nexora.adapters.trd_bot.models import CapabilitiesResponse
from nexora.trd_bot_sync import (
    EVENT_SYNC_JOB_TYPE,
    SNAPSHOT_SYNC_JOB_TYPE,
    TrdBotSyncHandlers,
    initial_event_sync_payload,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "contracts/integration/v1/fixtures"


def _json(name: str) -> dict[str, Any]:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _claim(payload: dict[str, Any], *, job_type: str = EVENT_SYNC_JOB_TYPE) -> JobClaim:
    from datetime import UTC, datetime, timedelta

    return JobClaim(
        job_id=uuid4(),
        owner_id=uuid4(),
        job_type=job_type,
        payload=payload,
        attempt_count=1,
        max_attempts=4,
        lease_expires_at=datetime.now(UTC) + timedelta(seconds=60),
    )


class FakeClient:
    def __init__(self, *, event_page: EventPage | Exception, snapshot_page: SnapshotPage | None = None) -> None:
        self.event_page = event_page
        self.snapshot_page = snapshot_page
        self.capabilities = CapabilitiesResponse.model_validate(_json("capabilities-response.json"))

    @property
    def negotiated_provider_version(self) -> str | None:
        return self.capabilities.provider_version

    def negotiate(self, *, correlation_id: object = None) -> CapabilitiesResponse:
        return self.capabilities

    def list_events(self, **_: object) -> EventPage:
        if isinstance(self.event_page, Exception):
            raise self.event_page
        return self.event_page

    def list_snapshots(self, resource_type: ResourceType, **_: object) -> SnapshotPage:
        assert isinstance(resource_type, ResourceType)
        assert self.snapshot_page is not None
        return self.snapshot_page


def _event_page(*, has_more: bool = False, schema: str = "decision-evaluation-completed-v1") -> EventPage:
    event = _json("decision-event.json")
    event["payload_schema"] = schema
    return EventPage.model_validate(
        {
            "schema_version": "trd-integration-event-page-v1",
            "events": [event],
            "next_cursor": "opaque-next" if has_more else None,
            "has_more": has_more,
        }
    )


def test_event_page_creates_atomic_evidence_checkpoint_outbox_and_continuation() -> None:
    completion = TrdBotSyncHandlers(FakeClient(event_page=_event_page(has_more=True))).sync_events(
        _claim(initial_event_sync_payload())
    )

    assert len(completion.sync_receipts) == 1
    assert completion.sync_receipts[0].status == "applied"
    assert len(completion.source_evidence) == 1
    assert completion.checkpoint is not None
    assert completion.checkpoint.cursor == "opaque-next"
    assert completion.checkpoint.expected_row_version is None
    assert completion.enqueue[0].job_type == EVENT_SYNC_JOB_TYPE
    assert completion.enqueue[0].payload["expected_checkpoint_version"] == 1
    assert completion.outbox[0].payload == {
        "schema_version": "nexora-trd-bot-sync-page-result-v1",
        "applied": 1,
        "quarantined": 0,
        "has_more": True,
    }


def test_unknown_payload_schema_is_quarantined_without_projection_evidence() -> None:
    completion = TrdBotSyncHandlers(FakeClient(event_page=_event_page(schema="future-decision-schema-v9"))).sync_events(
        _claim(initial_event_sync_payload())
    )

    assert completion.source_evidence == ()
    assert completion.sync_receipts[0].status == "quarantined"
    assert completion.sync_receipts[0].reason_code == "UNSUPPORTED_PAYLOAD_SCHEMA"
    assert completion.outbox[0].payload["quarantined"] == 1


def test_expired_cursor_resets_checkpoint_and_starts_ordered_snapshot_chain() -> None:
    expired = CursorExpiredError(410, "CURSOR_EXPIRED", retryable=False)
    payload = initial_event_sync_payload()
    payload["cursor"] = "expired-cursor"
    payload["expected_checkpoint_version"] = 7
    completion = TrdBotSyncHandlers(FakeClient(event_page=expired)).sync_events(_claim(payload))

    assert completion.checkpoint is not None
    assert completion.checkpoint.cursor is None
    assert completion.checkpoint.expected_row_version == 7
    assert len(completion.enqueue) == 1
    assert {job.job_type for job in completion.enqueue} == {SNAPSHOT_SYNC_JOB_TYPE}
    assert completion.enqueue[0].payload["resource_type"] == next(iter(ResourceType)).value
    assert completion.enqueue[0].payload["resource_index"] == 0
    assert completion.outbox[0].payload["reason_code"] == "CURSOR_EXPIRED"


def test_snapshot_page_persists_versioned_evidence_and_resumes_event_stream() -> None:
    page = SnapshotPage.model_validate(
        {
            "schema_version": "nexora-source-snapshot-page-v1",
            "items": [{"schema_version": "decision-evaluation-v1", "decision_evaluation_id": "decision-1"}],
            "next_cursor": None,
            "has_more": False,
        }
    )
    payload = {
        "schema_version": "nexora-trd-bot-snapshot-sync-job-v1",
        "resource_type": "decision_evaluation",
        "resource_index": len(ResourceType) - 1,
        "cursor": None,
        "expected_checkpoint_version": None,
        "resume_event_checkpoint_version": 8,
        "page_limit": 100,
    }
    completion = TrdBotSyncHandlers(FakeClient(event_page=_event_page(), snapshot_page=page)).sync_snapshot(
        _claim(payload, job_type=SNAPSHOT_SYNC_JOB_TYPE)
    )

    assert completion.source_evidence[0].source_entity_id == "decision-1"
    assert completion.checkpoint is not None
    assert completion.checkpoint.stream_name.endswith("generation:8")
    assert completion.enqueue[0].job_type == EVENT_SYNC_JOB_TYPE
    assert completion.enqueue[0].payload["expected_checkpoint_version"] == 8


def test_completed_snapshot_resource_enqueues_the_next_resource_before_event_resume() -> None:
    page = SnapshotPage.model_validate(
        {
            "schema_version": "nexora-source-snapshot-page-v1",
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }
    )
    payload = {
        "schema_version": "nexora-trd-bot-snapshot-sync-job-v1",
        "resource_type": next(iter(ResourceType)).value,
        "resource_index": 0,
        "cursor": None,
        "expected_checkpoint_version": None,
        "resume_event_checkpoint_version": 8,
        "page_limit": 100,
    }
    completion = TrdBotSyncHandlers(FakeClient(event_page=_event_page(), snapshot_page=page)).sync_snapshot(
        _claim(payload, job_type=SNAPSHOT_SYNC_JOB_TYPE)
    )

    assert completion.enqueue[0].job_type == SNAPSHOT_SYNC_JOB_TYPE
    assert completion.enqueue[0].payload["resource_index"] == 1


def test_sync_payload_rejects_unknown_fields() -> None:
    payload = initial_event_sync_payload()
    payload["exchange_api_key"] = "forbidden"
    with pytest.raises(ValueError):
        TrdBotSyncHandlers(FakeClient(event_page=_event_page())).sync_events(_claim(payload))
