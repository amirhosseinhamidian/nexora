from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, Final, Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field

from nexora.adapters.postgresql import (
    ActiveProjectionGeneration,
    AggregateProjectionState,
    CheckpointAdvance,
    DecisionProjectionMutation,
    DecisionProjectionQuarantineWrite,
    EnqueuedJob,
    JobClaim,
    JobCompletion,
    OutboxMessage,
    SourceEvidenceWrite,
    SyncReceiptWrite,
)
from nexora.adapters.trd_bot import CONTRACT_VERSION, CursorExpiredError, EventPage, ResourceType, SnapshotPage
from nexora.adapters.trd_bot.models import CapabilitiesResponse, EventEnvelope
from nexora.decision_event_projection import (
    EVENT_SCHEMA_ALLOWLIST,
    PROJECTED_RESOURCE_KINDS,
    DecisionProjectionRecord,
    project_event,
    project_snapshot,
)
from nexora.paper_shadow_projection import (
    EVENT_PAYLOAD_SCHEMAS,
    validate_projection_event,
    validate_projection_snapshot,
)

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


class DecisionProjectionReader(Protocol):
    def active_generation(self, owner_id: UUID) -> ActiveProjectionGeneration | None: ...

    def aggregate_state(
        self, owner_id: UUID, aggregate_type: str, aggregate_id: str
    ) -> AggregateProjectionState | None: ...


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
    trigger: Literal["cursor_expired", "aggregate_gap", "checksum_mismatch"] = "cursor_expired"


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

    def __init__(self, client: SyncClient, decision_projection: DecisionProjectionReader | None = None) -> None:
        self._client = client
        self._decision_projection = decision_projection

    def registry(self) -> dict[str, Callable[[JobClaim], JobCompletion]]:
        return {
            EVENT_SYNC_JOB_TYPE: self.sync_events,
            SNAPSHOT_SYNC_JOB_TYPE: self.sync_snapshot,
        }

    def sync_events(self, claim: JobClaim) -> JobCompletion:
        job = EventSyncJob.model_validate(claim.payload)
        capabilities = self._client.negotiate()
        projection_reader = self._decision_projection
        active_generation = None if projection_reader is None else projection_reader.active_generation(claim.owner_id)
        if projection_reader is not None and active_generation is None:
            return self._full_resync_completion(
                job,
                capabilities,
                reason_code="INITIAL_SNAPSHOT_REQUIRED",
                trigger="cursor_expired",
            )
        try:
            page = self._client.list_events(cursor=job.cursor, limit=job.page_limit)
        except CursorExpiredError:
            return self._full_resync_completion(
                job, capabilities, reason_code="CURSOR_EXPIRED", trigger="cursor_expired"
            )

        receipts: list[SyncReceiptWrite] = []
        evidence: list[SourceEvidenceWrite] = []
        projected_events: list[DecisionProjectionRecord] = []
        observed_versions: dict[str, tuple[int, str | None, str]] = {}
        applied = 0
        quarantined = 0
        for event in page.events:
            envelope = event.model_dump(mode="json")
            envelope_hash = canonical_json_sha256(envelope)
            decision_schemas = EVENT_SCHEMA_ALLOWLIST.get(event.event_type)
            supported_schema = SUPPORTED_PAYLOAD_SCHEMAS.get(event.event_type.value)
            is_supported = (
                event.payload_schema in decision_schemas
                if decision_schemas is not None
                else supported_schema == event.payload_schema
            )
            reason_code = None if is_supported else "UNSUPPORTED_PAYLOAD_SCHEMA"
            if is_supported and event.event_type in EVENT_PAYLOAD_SCHEMAS:
                try:
                    validate_projection_event(event)
                except ValueError:
                    is_supported = False
                    reason_code = "INVALID_PROJECTION_PAYLOAD"
            projected: DecisionProjectionRecord | None = None
            if is_supported and active_generation is not None and event.event_type in EVENT_SCHEMA_ALLOWLIST:
                try:
                    projected = project_event(event, provider_release=capabilities.provider_version)
                except ValueError:
                    return self._projection_recovery_completion(
                        job,
                        capabilities,
                        active_generation,
                        event,
                        "INVALID_DECISION_PROJECTION",
                        trigger="checksum_mismatch",
                    )
            if projected is not None:
                assert active_generation is not None
                assert projected.aggregate_type is not None
                assert projected.aggregate_id is not None
                assert projected.aggregate_version is not None
                aggregate_key = f"{projected.aggregate_type}:{projected.aggregate_id}"
                current = observed_versions.get(aggregate_key)
                if current is None:
                    assert projection_reader is not None
                    stored = projection_reader.aggregate_state(
                        claim.owner_id, projected.aggregate_type, projected.aggregate_id
                    )
                    current = (
                        (0, None, "") if stored is None else (stored.version, stored.event_id, stored.payload_sha256)
                    )
                current_version, current_event_id, current_checksum = current
                if projected.aggregate_version <= current_version:
                    duplicate = (
                        projected.aggregate_version == current_version
                        and projected.source_event_id == current_event_id
                        and projected.payload_sha256 == current_checksum
                    )
                    if not duplicate:
                        return self._projection_recovery_completion(
                            job,
                            capabilities,
                            active_generation,
                            event,
                            "AGGREGATE_VERSION_CONFLICT",
                            trigger="aggregate_gap",
                        )
                    projected = None
                elif projected.aggregate_version != current_version + 1:
                    return self._projection_recovery_completion(
                        job,
                        capabilities,
                        active_generation,
                        event,
                        "AGGREGATE_VERSION_GAP",
                        trigger="aggregate_gap",
                    )
                else:
                    observed_versions[aggregate_key] = (
                        projected.aggregate_version,
                        projected.source_event_id,
                        projected.payload_sha256,
                    )
                    projected_events.append(projected)
            receipts.append(
                SyncReceiptWrite(
                    event_id=event.event_id,
                    event_type=event.event_type.value,
                    payload_schema=event.payload_schema,
                    provider_version=capabilities.provider_version,
                    status="applied" if is_supported else "quarantined",
                    reason_code=reason_code,
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
            decision_projection=(
                None
                if active_generation is None or not projected_events
                else DecisionProjectionMutation(
                    generation=active_generation.generation,
                    trigger=active_generation.trigger,
                    provider_version=active_generation.provider_version,
                    contract_version=active_generation.contract_version,
                    events=tuple(projected_events),
                )
            ),
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
        projected_snapshots: list[DecisionProjectionRecord] = []
        decision_quarantine: list[DecisionProjectionQuarantineWrite] = []
        applied = 0
        quarantined = 0
        decision_resource = job.resource_type in PROJECTED_RESOURCE_KINDS
        projection_resource = job.resource_type in {
            ResourceType.PAPER_SHADOW_PORTFOLIO,
            ResourceType.PAPER_SHADOW_POSITION,
        }
        for item in page.items:
            if decision_resource:
                digest = canonical_json_sha256(item)
                reference = item.get("source_reference")
                reference_dict = reference if isinstance(reference, dict) else {}
                entity_id = reference_dict.get("resource_id")
                schema = reference_dict.get("resource_schema_version")
                resolved_id = entity_id if isinstance(entity_id, str) and entity_id else f"snapshot-{digest[:40]}"
                resolved_schema = schema if isinstance(schema, str) and schema else "missing"
                try:
                    projected = project_snapshot(
                        job.resource_type,
                        item,
                        provider_release=capabilities.provider_version,
                    )
                except ValueError:
                    quarantined += 1
                    decision_quarantine.append(
                        DecisionProjectionQuarantineWrite(
                            resource_type=job.resource_type.value,
                            resource_id=resolved_id,
                            source_schema_version=resolved_schema,
                            source_event_id=None,
                            reason_code="INVALID_OR_UNSUPPORTED_SNAPSHOT",
                            payload=dict(item),
                            payload_sha256=digest,
                        )
                    )
                    evidence.append(
                        self._snapshot_evidence(
                            claim,
                            capabilities,
                            job.resource_type,
                            item,
                            digest,
                            resolved_id,
                            schema=resolved_schema,
                            quarantined=True,
                        )
                    )
                    continue
                applied += 1
                projected_snapshots.append(projected)
                evidence.append(
                    self._snapshot_evidence(
                        claim,
                        capabilities,
                        job.resource_type,
                        item,
                        digest,
                        projected.resource_id,
                        schema=projected.source_schema_version,
                        quarantined=False,
                    )
                )
                continue
            schema = item.get("schema_version")
            digest = canonical_json_sha256(item)
            entity_id = self._snapshot_entity_id(job.resource_type, item, digest)
            if not isinstance(schema, str) or not schema:
                if projection_resource:
                    quarantined += 1
                    evidence.append(
                        self._snapshot_evidence(
                            claim,
                            capabilities,
                            job.resource_type,
                            item,
                            digest,
                            entity_id,
                            schema="missing",
                            quarantined=True,
                        )
                    )
                    continue
                raise ValueError("snapshot item schema_version is required")
            try:
                validate_projection_snapshot(job.resource_type, item)
            except ValueError:
                if projection_resource:
                    quarantined += 1
                    evidence.append(
                        self._snapshot_evidence(
                            claim,
                            capabilities,
                            job.resource_type,
                            item,
                            digest,
                            entity_id,
                            schema=schema,
                            quarantined=True,
                        )
                    )
                    continue
                raise
            applied += 1
            evidence.append(
                self._snapshot_evidence(
                    claim,
                    capabilities,
                    job.resource_type,
                    item,
                    digest,
                    entity_id,
                    schema=schema,
                    quarantined=False,
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
                    trigger=job.trigger,
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
        outbox = (
            (
                OutboxMessage(
                    event_type="trd_bot.sync.projection_snapshot.completed.v1",
                    aggregate_type="trd_bot_projection_snapshot",
                    aggregate_id=job.resource_type.value,
                    idempotency_key=_job_key(
                        "trd-projection-snapshot-page",
                        job.resource_type.value,
                        job.cursor,
                        str(job.resume_event_checkpoint_version),
                    ),
                    payload={
                        "schema_version": "nexora-trd-bot-projection-snapshot-result-v1",
                        "resource_type": job.resource_type.value,
                        "applied": applied,
                        "quarantined": quarantined,
                        "has_more": page.has_more,
                    },
                ),
            )
            if projection_resource or decision_resource
            else ()
        )
        activate_decision_projection = (
            decision_resource and job.resource_type is ResourceType.ALERT_OUTCOME and not page.has_more
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
            enqueue=() if activate_decision_projection else tuple(follow_up),
            enqueue_after_projection_activation=(tuple(follow_up) if activate_decision_projection else ()),
            decision_projection=(
                None
                if not decision_resource
                else DecisionProjectionMutation(
                    generation=job.resume_event_checkpoint_version,
                    trigger=job.trigger,
                    provider_version=capabilities.provider_version,
                    contract_version=CONTRACT_VERSION,
                    snapshots=tuple(projected_snapshots),
                    resource_type=job.resource_type.value,
                    resource_item_count=len(page.items),
                    resource_quarantine_count=quarantined,
                    resource_completed=not page.has_more,
                    quarantine=tuple(decision_quarantine),
                    activate=activate_decision_projection,
                )
            ),
            outbox=outbox,
        )

    def _full_resync_completion(
        self,
        job: EventSyncJob,
        capabilities: CapabilitiesResponse,
        *,
        reason_code: str,
        trigger: Literal["cursor_expired", "aggregate_gap", "checksum_mismatch"],
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
                    trigger=trigger,
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
                        "reason_code": reason_code,
                    },
                ),
            ),
        )

    def _projection_recovery_completion(
        self,
        job: EventSyncJob,
        capabilities: CapabilitiesResponse,
        active: ActiveProjectionGeneration,
        event: EventEnvelope,
        reason_code: str,
        *,
        trigger: Literal["aggregate_gap", "checksum_mismatch"],
    ) -> JobCompletion:
        completion = self._full_resync_completion(
            job,
            capabilities,
            reason_code=reason_code,
            trigger=trigger,
        )
        envelope = event.model_dump(mode="json")
        digest = canonical_json_sha256(envelope)
        return JobCompletion(
            checkpoint=completion.checkpoint,
            enqueue=completion.enqueue,
            outbox=completion.outbox,
            sync_receipts=(
                SyncReceiptWrite(
                    event_id=event.event_id,
                    event_type=event.event_type.value,
                    payload_schema=event.payload_schema,
                    provider_version=capabilities.provider_version,
                    status="quarantined",
                    reason_code=reason_code,
                    envelope=envelope,
                    envelope_sha256=digest,
                ),
            ),
            decision_projection=DecisionProjectionMutation(
                generation=active.generation,
                trigger=active.trigger,
                provider_version=active.provider_version,
                contract_version=active.contract_version,
                quarantine=(
                    DecisionProjectionQuarantineWrite(
                        resource_type=event.source.resource_type,
                        resource_id=event.source.resource_id,
                        source_schema_version=event.payload_schema,
                        source_event_id=event.event_id,
                        reason_code=reason_code,
                        payload=envelope,
                        payload_sha256=digest,
                    ),
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

    @staticmethod
    def _snapshot_evidence(
        claim: JobClaim,
        capabilities: CapabilitiesResponse,
        resource_type: ResourceType,
        item: dict[str, Any],
        digest: str,
        entity_id: str,
        *,
        schema: str,
        quarantined: bool,
    ) -> SourceEvidenceWrite:
        prefix = "quarantine.snapshot" if quarantined else "snapshot"
        return SourceEvidenceWrite(
            source_entity_type=f"{prefix}.{resource_type.value}",
            source_entity_id=entity_id,
            source_schema_version=schema,
            source_version=f"{capabilities.provider_version}:{digest[:16]}",
            source_observed_at=capabilities.generated_at,
            correlation_id=uuid5(
                NAMESPACE_URL,
                f"nexora:{claim.owner_id}:{resource_type.value}:{digest}",
            ),
            payload=dict(item),
            payload_sha256=digest,
        )
