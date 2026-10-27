from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, Final, Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field

from nexora.adapters.postgresql import (
    CheckpointAdvance,
    EnqueuedJob,
    JobClaim,
    JobCompletion,
    OutboxMessage,
    SourceEvidenceWrite,
    SyncReceiptWrite,
)
from nexora.adapters.trd_bot import CONTRACT_VERSION, CursorExpiredError, EventPage, ResourceType, SnapshotPage
from nexora.adapters.trd_bot.models import CapabilitiesResponse

EVENT_SYNC_JOB_TYPE: Final = "trd_bot.event_sync"
SNAPSHOT_SYNC_JOB_TYPE: Final = "trd_bot.snapshot_sync"
SYNC_CONSUMER: Final = "nexora_trd_bot_sync_v1"
EVENT_STREAM: Final = "events"

SUPPORTED_PAYLOAD_SCHEMAS: Final = {
    "market_context.assessed.v1": "market-context-assessed-v1",
    "decision.evaluation.completed.v1": "decision-evaluation-completed-v1",
    "candidate.state.changed.v1": "candidate-state-changed-v1",
    "risk_gate.completed.v1": "risk-gate-completed-v1",
    "portfolio_intelligence.completed.v1": "portfolio-intelligence-completed-v1",
    "alert.published.v1": "alert-published-v1",
    "alert.lifecycle.changed.v1": "alert-lifecycle-changed-v1",
    "simulation.position.opened.v1": "simulation-position-opened-v1",
    "simulation.position.updated.v1": "simulation-position-updated-v1",
    "simulation.position.closed.v1": "simulation-position-closed-v1",
    "outcome.recorded.v1": "outcome-recorded-v1",
}


class SyncClient(Protocol):
    @property
    def negotiated_provider_version(self) -> str | None: ...

    def negotiate(self, *, correlation_id: UUID | None = None) -> CapabilitiesResponse: ...

    def list_events(
        self,
        *,
        cursor: str | None = None,
        limit: int = 100,
        correlation_id: UUID | None = None,
    ) -> EventPage: ...

    def list_snapshots(
        self,
        resource_type: ResourceType,
        *,
        cursor: str | None = None,
        limit: int = 100,
        correlation_id: UUID | None = None,
    ) -> SnapshotPage: ...


class EventSyncJob(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["nexora-trd-bot-event-sync-job-v1"]
    cursor: str | None
    expected_checkpoint_version: int | None = Field(ge=1)
    page_limit: int = Field(default=100, ge=1, le=500)


class SnapshotSyncJob(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["nexora-trd-bot-snapshot-sync-job-v1"]
    resource_type: ResourceType
    resource_index: int = Field(ge=0, lt=len(ResourceType))
    cursor: str | None
    expected_checkpoint_version: int | None = Field(ge=1)
    resume_event_checkpoint_version: int = Field(ge=1)
    page_limit: int = Field(default=100, ge=1, le=500)


def canonical_json_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _job_key(prefix: str, *parts: str | None) -> str:
    digest = hashlib.sha256("\x1f".join(part or "initial" for part in parts).encode()).hexdigest()[:32]
    return f"{prefix}-{digest}"


def initial_event_sync_payload(*, page_limit: int = 100) -> dict[str, Any]:
    return EventSyncJob(
        schema_version="nexora-trd-bot-event-sync-job-v1",
        cursor=None,
        expected_checkpoint_version=None,
        page_limit=page_limit,
    ).model_dump(mode="json")


class TrdBotSyncHandlers:
    """Translate bounded TRD Bot pages into one atomic durable-work completion."""

    def __init__(self, client: SyncClient) -> None:
        self._client = client

    def registry(self) -> dict[str, Callable[[JobClaim], JobCompletion]]:
        return {
            EVENT_SYNC_JOB_TYPE: self.sync_events,
            SNAPSHOT_SYNC_JOB_TYPE: self.sync_snapshot,
        }

    def sync_events(self, claim: JobClaim) -> JobCompletion:
        job = EventSyncJob.model_validate(claim.payload)
        capabilities = self._client.negotiate()
        try:
            page = self._client.list_events(cursor=job.cursor, limit=job.page_limit)
        except CursorExpiredError:
            return self._cursor_expired_completion(job, capabilities)

        receipts: list[SyncReceiptWrite] = []
        evidence: list[SourceEvidenceWrite] = []
        applied = 0
        quarantined = 0
        for event in page.events:
            envelope = event.model_dump(mode="json")
            envelope_hash = canonical_json_sha256(envelope)
            supported_schema = SUPPORTED_PAYLOAD_SCHEMAS.get(event.event_type.value)
            is_supported = supported_schema == event.payload_schema
            receipts.append(
                SyncReceiptWrite(
                    event_id=event.event_id,
                    event_type=event.event_type.value,
                    payload_schema=event.payload_schema,
                    provider_version=capabilities.provider_version,
                    status="applied" if is_supported else "quarantined",
                    reason_code=None if is_supported else "UNSUPPORTED_PAYLOAD_SCHEMA",
                    envelope=envelope,
                    envelope_sha256=envelope_hash,
                )
            )
            if is_supported:
                applied += 1
                evidence.append(
                    SourceEvidenceWrite(
                        source_entity_type=event.event_type.value,
                        source_entity_id=event.event_id,
                        source_schema_version=event.schema_version,
                        source_version=capabilities.provider_version,
                        source_observed_at=event.occurred_at,
                        correlation_id=event.correlation_id,
                        payload=envelope,
                        payload_sha256=envelope_hash,
                    )
                )
            else:
                quarantined += 1

        next_version = (job.expected_checkpoint_version or 0) + 1
        next_jobs: tuple[EnqueuedJob, ...] = ()
        if page.has_more:
            assert page.next_cursor is not None
            payload = EventSyncJob(
                schema_version="nexora-trd-bot-event-sync-job-v1",
                cursor=page.next_cursor,
                expected_checkpoint_version=next_version,
                page_limit=job.page_limit,
            ).model_dump(mode="json")
            next_jobs = (
                EnqueuedJob(
                    job_type=EVENT_SYNC_JOB_TYPE,
                    idempotency_key=_job_key("trd-event-page", page.next_cursor),
                    payload=payload,
                ),
            )
        last_event_id = page.events[-1].event_id if page.events else None
        return JobCompletion(
            checkpoint=CheckpointAdvance(
                consumer_name=SYNC_CONSUMER,
                stream_name=EVENT_STREAM,
                cursor=page.next_cursor,
                last_event_id=last_event_id,
                provider_version=capabilities.provider_version,
                contract_version=CONTRACT_VERSION,
                expected_row_version=job.expected_checkpoint_version,
            ),
            sync_receipts=tuple(receipts),
            source_evidence=tuple(evidence),
            enqueue=next_jobs,
            outbox=(
                OutboxMessage(
                    event_type="trd_bot.sync.page.completed.v1",
                    aggregate_type="trd_bot_event_stream",
                    aggregate_id=EVENT_STREAM,
                    idempotency_key=_job_key("trd-event-page-complete", job.cursor),
                    payload={
                        "schema_version": "nexora-trd-bot-sync-page-result-v1",
                        "applied": applied,
                        "quarantined": quarantined,
                        "has_more": page.has_more,
                    },
                ),
            ),
        )

    def sync_snapshot(self, claim: JobClaim) -> JobCompletion:
        job = SnapshotSyncJob.model_validate(claim.payload)
        capabilities = self._client.negotiate()
        page = self._client.list_snapshots(job.resource_type, cursor=job.cursor, limit=job.page_limit)
        evidence: list[SourceEvidenceWrite] = []
        for item in page.items:
            schema = item.get("schema_version")
            if not isinstance(schema, str) or not schema:
                raise ValueError("snapshot item schema_version is required")
            digest = canonical_json_sha256(item)
            entity_id = self._snapshot_entity_id(job.resource_type, item, digest)
            evidence.append(
                SourceEvidenceWrite(
                    source_entity_type=f"snapshot.{job.resource_type.value}",
                    source_entity_id=entity_id,
                    source_schema_version=schema,
                    source_version=f"{capabilities.provider_version}:{digest[:16]}",
                    source_observed_at=capabilities.generated_at,
                    correlation_id=uuid5(
                        NAMESPACE_URL,
                        f"nexora:{claim.owner_id}:{job.resource_type.value}:{digest}",
                    ),
                    payload=dict(item),
                    payload_sha256=digest,
                )
            )

        next_version = (job.expected_checkpoint_version or 0) + 1
        follow_up: list[EnqueuedJob] = []
        if page.has_more:
            assert page.next_cursor is not None
            payload = job.model_copy(
                update={"cursor": page.next_cursor, "expected_checkpoint_version": next_version}
            ).model_dump(mode="json")
            follow_up.append(
                EnqueuedJob(
                    job_type=SNAPSHOT_SYNC_JOB_TYPE,
                    idempotency_key=_job_key("trd-snapshot-page", job.resource_type.value, page.next_cursor),
                    payload=payload,
                )
            )
        else:
            resources = tuple(ResourceType)
            next_index = job.resource_index + 1
            if next_index < len(resources):
                next_resource = resources[next_index]
                payload = SnapshotSyncJob(
                    schema_version="nexora-trd-bot-snapshot-sync-job-v1",
                    resource_type=next_resource,
                    resource_index=next_index,
                    cursor=None,
                    expected_checkpoint_version=None,
                    resume_event_checkpoint_version=job.resume_event_checkpoint_version,
                    page_limit=job.page_limit,
                ).model_dump(mode="json")
                follow_up.append(
                    EnqueuedJob(
                        job_type=SNAPSHOT_SYNC_JOB_TYPE,
                        idempotency_key=_job_key(
                            "trd-full-resync",
                            next_resource.value,
                            str(job.resume_event_checkpoint_version),
                        ),
                        payload=payload,
                    )
                )
            else:
                payload = EventSyncJob(
                    schema_version="nexora-trd-bot-event-sync-job-v1",
                    cursor=None,
                    expected_checkpoint_version=job.resume_event_checkpoint_version,
                    page_limit=job.page_limit,
                ).model_dump(mode="json")
                follow_up.append(
                    EnqueuedJob(
                        job_type=EVENT_SYNC_JOB_TYPE,
                        idempotency_key=_job_key("trd-event-resume", str(job.resume_event_checkpoint_version)),
                        payload=payload,
                    )
                )
        return JobCompletion(
            checkpoint=CheckpointAdvance(
                consumer_name=SYNC_CONSUMER,
                stream_name=(f"snapshot:{job.resource_type.value}:generation:{job.resume_event_checkpoint_version}"),
                cursor=page.next_cursor,
                last_event_id=None,
                provider_version=capabilities.provider_version,
                contract_version=CONTRACT_VERSION,
                expected_row_version=job.expected_checkpoint_version,
            ),
            source_evidence=tuple(evidence),
            enqueue=tuple(follow_up),
        )

    def _cursor_expired_completion(
        self,
        job: EventSyncJob,
        capabilities: CapabilitiesResponse,
    ) -> JobCompletion:
        reset_version = (job.expected_checkpoint_version or 0) + 1
        first_resource = next(iter(ResourceType))
        jobs = (
            EnqueuedJob(
                job_type=SNAPSHOT_SYNC_JOB_TYPE,
                idempotency_key=_job_key("trd-full-resync", first_resource.value, str(reset_version)),
                payload=SnapshotSyncJob(
                    schema_version="nexora-trd-bot-snapshot-sync-job-v1",
                    resource_type=first_resource,
                    resource_index=0,
                    cursor=None,
                    expected_checkpoint_version=None,
                    resume_event_checkpoint_version=reset_version,
                    page_limit=job.page_limit,
                ).model_dump(mode="json"),
            ),
        )
        return JobCompletion(
            checkpoint=CheckpointAdvance(
                consumer_name=SYNC_CONSUMER,
                stream_name=EVENT_STREAM,
                cursor=None,
                last_event_id=None,
                provider_version=capabilities.provider_version,
                contract_version=CONTRACT_VERSION,
                expected_row_version=job.expected_checkpoint_version,
            ),
            enqueue=jobs,
            outbox=(
                OutboxMessage(
                    event_type="trd_bot.sync.full_resync.required.v1",
                    aggregate_type="trd_bot_event_stream",
                    aggregate_id=EVENT_STREAM,
                    idempotency_key=_job_key("trd-full-resync-required", str(reset_version)),
                    payload={
                        "schema_version": "nexora-trd-bot-full-resync-required-v1",
                        "resource_count": len(ResourceType),
                        "reason_code": "CURSOR_EXPIRED",
                    },
                ),
            ),
        )

    @staticmethod
    def _snapshot_entity_id(resource_type: ResourceType, item: dict[str, Any], digest: str) -> str:
        candidates = ("id", f"{resource_type.value}_id", "resource_id")
        for key in candidates:
            value = item.get(key)
            if isinstance(value, str) and value:
                return value[:128]
        return f"snapshot-{digest[:40]}"
