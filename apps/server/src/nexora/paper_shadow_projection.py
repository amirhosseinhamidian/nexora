from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from nexora.adapters.trd_bot.models import EventEnvelope, EventType, ResourceType

PORTFOLIO_SNAPSHOT_SCHEMA = "trd-paper-shadow-portfolio-v1"
POSITION_SNAPSHOT_SCHEMA = "trd-paper-shadow-position-v1"
PROJECTION_VERSION: Literal["nexora-trd-bot-paper-shadow-projection-v1"] = "nexora-trd-bot-paper-shadow-projection-v1"

ProjectionMode = Literal["paper", "shadow"]
ProjectionIssueCode = Literal[
    "NO_EVIDENCE",
    "CHECKSUM_MISMATCH",
    "UNSUPPORTED_SCHEMA",
    "INVALID_PAYLOAD",
    "VERSION_CONFLICT",
    "AGGREGATE_GAP",
    "PORTFOLIO_MISSING",
    "MODE_MISMATCH",
    "INVALID_TRANSITION",
]
DecimalString = Annotated[Decimal, Field(ge=0)]
PositiveDecimalString = Annotated[Decimal, Field(gt=0)]

EVENT_PAYLOAD_SCHEMAS: dict[EventType, str] = {
    EventType.SIMULATION_POSITION_OPENED: "simulation-position-opened-v1",
    EventType.SIMULATION_POSITION_UPDATED: "simulation-position-updated-v1",
    EventType.SIMULATION_POSITION_CLOSED: "simulation-position-closed-v1",
}


class ProjectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware UTC")
    return value


def _require_decimal_string(value: object) -> object:
    if not isinstance(value, str):
        raise ValueError("financial decimal values must be encoded as strings")
    if not value or value.startswith("+") or "e" in value.lower():
        raise ValueError("financial decimal string is not canonical")
    return value


class PaperShadowPortfolioSnapshot(ProjectionModel):
    schema_version: Literal["trd-paper-shadow-portfolio-v1"]
    paper_shadow_portfolio_id: str = Field(min_length=1, max_length=160)
    mode: ProjectionMode
    name: str = Field(min_length=1, max_length=160)
    base_asset_symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9._-]{0,23}$")
    status: Literal["active", "closed"]
    aggregate_version: int = Field(ge=1)
    as_of: datetime

    _as_of_is_utc = field_validator("as_of")(_require_utc)


class PaperShadowPositionSnapshot(ProjectionModel):
    schema_version: Literal["trd-paper-shadow-position-v1"]
    paper_shadow_position_id: str = Field(min_length=1, max_length=160)
    paper_shadow_portfolio_id: str = Field(min_length=1, max_length=160)
    mode: ProjectionMode
    asset_symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9._-]{0,23}$")
    quantity: DecimalString
    average_entry_price: PositiveDecimalString | None
    status: Literal["open", "closed"]
    aggregate_version: int = Field(ge=1)
    as_of: datetime

    _quantity_is_string = field_validator("quantity", mode="before")(_require_decimal_string)
    _average_price_is_string = field_validator("average_entry_price", mode="before")(
        lambda value: None if value is None else _require_decimal_string(value)
    )
    _as_of_is_utc = field_validator("as_of")(_require_utc)

    @model_validator(mode="after")
    def validate_state(self) -> PaperShadowPositionSnapshot:
        if self.status == "open" and (self.quantity <= 0 or self.average_entry_price is None):
            raise ValueError("an open position requires positive quantity and average entry price")
        if self.status == "closed" and self.quantity != 0:
            raise ValueError("a closed position requires zero quantity")
        return self


class SimulationPositionPayload(ProjectionModel):
    position_id: str = Field(min_length=1, max_length=160)
    portfolio_id: str = Field(min_length=1, max_length=160)
    mode: ProjectionMode
    asset_symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9._-]{0,23}$")
    quantity: DecimalString
    average_entry_price: PositiveDecimalString | None

    _quantity_is_string = field_validator("quantity", mode="before")(_require_decimal_string)
    _average_price_is_string = field_validator("average_entry_price", mode="before")(
        lambda value: None if value is None else _require_decimal_string(value)
    )


class ProjectionSourceEvidence(ProjectionModel):
    source_reference_id: UUID
    source_entity_type: str = Field(min_length=1, max_length=80)
    source_entity_id: str = Field(min_length=1, max_length=160)
    source_schema_version: str = Field(min_length=1, max_length=160)
    source_version: str = Field(min_length=1, max_length=160)
    source_observed_at: datetime
    payload: dict[str, Any]
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    _observed_at_is_utc = field_validator("source_observed_at")(_require_utc)


class ProjectionLineage(ProjectionModel):
    source_reference_id: UUID
    source_entity_type: str
    source_entity_id: str
    source_schema_version: str
    source_version: str
    source_observed_at: datetime
    payload_sha256: str


class PaperShadowPortfolioProjection(ProjectionModel):
    portfolio_id: str
    mode: ProjectionMode
    name: str
    base_asset_symbol: str
    status: Literal["active", "closed"]
    aggregate_version: int
    as_of: datetime
    lineage: ProjectionLineage


class PaperShadowPositionProjection(ProjectionModel):
    position_id: str
    portfolio_id: str
    mode: ProjectionMode
    asset_symbol: str
    quantity: Decimal
    average_entry_price: Decimal | None
    status: Literal["open", "closed"]
    aggregate_version: int
    as_of: datetime
    lineage: ProjectionLineage


class ProjectionIssue(ProjectionModel):
    code: ProjectionIssueCode
    source_reference_id: UUID | None
    source_entity_id: str | None
    message: str = Field(min_length=1, max_length=240)


class PaperShadowProjectionView(ProjectionModel):
    projection_version: Literal["nexora-trd-bot-paper-shadow-projection-v1"]
    complete: bool
    evidence_count: int = Field(ge=0)
    portfolios: tuple[PaperShadowPortfolioProjection, ...]
    positions: tuple[PaperShadowPositionProjection, ...]
    issues: tuple[ProjectionIssue, ...]
    projection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _lineage(evidence: ProjectionSourceEvidence) -> ProjectionLineage:
    return ProjectionLineage(
        source_reference_id=evidence.source_reference_id,
        source_entity_type=evidence.source_entity_type,
        source_entity_id=evidence.source_entity_id,
        source_schema_version=evidence.source_schema_version,
        source_version=evidence.source_version,
        source_observed_at=evidence.source_observed_at,
        payload_sha256=evidence.payload_sha256,
    )


def _issue(
    code: ProjectionIssueCode,
    evidence: ProjectionSourceEvidence | None,
    message: str,
) -> ProjectionIssue:
    return ProjectionIssue(
        code=code,
        source_reference_id=None if evidence is None else evidence.source_reference_id,
        source_entity_id=None if evidence is None else evidence.source_entity_id,
        message=message,
    )


def _payload_model(event: EventEnvelope) -> SimulationPositionPayload:
    expected_schema = EVENT_PAYLOAD_SCHEMAS.get(event.event_type)
    if expected_schema is None or event.payload_schema != expected_schema:
        raise ValueError("unsupported Paper/Shadow event payload schema")
    payload = SimulationPositionPayload.model_validate(event.payload)
    if event.aggregate.type != "paper_shadow_position" or event.aggregate.id != payload.position_id:
        raise ValueError("event aggregate does not match the projected position")
    if event.source.resource_type != "paper_shadow_position" or event.source.resource_id != payload.position_id:
        raise ValueError("event source does not match the projected position")
    if event.event_type is EventType.SIMULATION_POSITION_CLOSED:
        if payload.quantity != 0:
            raise ValueError("a closed position event requires zero quantity")
    elif payload.quantity <= 0 or payload.average_entry_price is None:
        raise ValueError("an open position event requires positive quantity and average entry price")
    return payload


def validate_projection_event(event: EventEnvelope) -> None:
    if event.event_type in EVENT_PAYLOAD_SCHEMAS:
        _payload_model(event)


def validate_projection_snapshot(resource_type: ResourceType, payload: dict[str, Any]) -> None:
    if resource_type is ResourceType.PAPER_SHADOW_PORTFOLIO:
        PaperShadowPortfolioSnapshot.model_validate(payload)
    elif resource_type is ResourceType.PAPER_SHADOW_POSITION:
        PaperShadowPositionSnapshot.model_validate(payload)


def _evidence_sort_key(evidence: ProjectionSourceEvidence) -> tuple[datetime, int, str, int, str, str]:
    rank = {
        "snapshot.paper_shadow_portfolio": 0,
        "snapshot.paper_shadow_position": 1,
        EventType.SIMULATION_POSITION_OPENED.value: 2,
        EventType.SIMULATION_POSITION_UPDATED.value: 2,
        EventType.SIMULATION_POSITION_CLOSED.value: 2,
    }.get(evidence.source_entity_type, 3)
    aggregate_id = evidence.source_entity_id
    aggregate_version = evidence.payload.get("aggregate_version", 0)
    aggregate = evidence.payload.get("aggregate")
    if isinstance(aggregate, dict):
        candidate_id = aggregate.get("id")
        candidate_version = aggregate.get("version")
        if isinstance(candidate_id, str):
            aggregate_id = candidate_id
        if isinstance(candidate_version, int):
            aggregate_version = candidate_version
    if not isinstance(aggregate_version, int):
        aggregate_version = 0
    return (
        evidence.source_observed_at,
        rank,
        aggregate_id,
        aggregate_version,
        evidence.source_entity_id,
        evidence.source_version,
    )


def rebuild_paper_shadow_projection(
    evidence_items: Iterable[ProjectionSourceEvidence],
) -> PaperShadowProjectionView:
    evidence = tuple(sorted(evidence_items, key=_evidence_sort_key))
    portfolios: dict[str, PaperShadowPortfolioProjection] = {}
    positions: dict[str, PaperShadowPositionProjection] = {}
    issues: list[ProjectionIssue] = []

    if not evidence:
        issues.append(_issue("NO_EVIDENCE", None, "no compatible Paper/Shadow evidence is available"))

    for item in evidence:
        if canonical_json_sha256(item.payload) != item.payload_sha256:
            issues.append(_issue("CHECKSUM_MISMATCH", item, "immutable evidence checksum does not match payload"))
            continue
        try:
            if item.source_entity_type == "snapshot.paper_shadow_portfolio":
                if item.payload.get("schema_version") != PORTFOLIO_SNAPSHOT_SCHEMA:
                    issues.append(_issue("UNSUPPORTED_SCHEMA", item, "unsupported portfolio snapshot schema"))
                    continue
                portfolio_snapshot = PaperShadowPortfolioSnapshot.model_validate(item.payload)
                if item.source_schema_version != portfolio_snapshot.schema_version:
                    raise ValueError("portfolio snapshot schema lineage does not match payload")
                if item.source_entity_id != portfolio_snapshot.paper_shadow_portfolio_id:
                    raise ValueError("portfolio snapshot identity does not match source lineage")
                current_portfolio = portfolios.get(portfolio_snapshot.paper_shadow_portfolio_id)
                if (
                    current_portfolio is not None
                    and portfolio_snapshot.aggregate_version <= current_portfolio.aggregate_version
                ):
                    code: ProjectionIssueCode = "VERSION_CONFLICT"
                    issues.append(_issue(code, item, "portfolio snapshot version is not newer than current evidence"))
                    continue
                portfolios[portfolio_snapshot.paper_shadow_portfolio_id] = PaperShadowPortfolioProjection(
                    portfolio_id=portfolio_snapshot.paper_shadow_portfolio_id,
                    mode=portfolio_snapshot.mode,
                    name=portfolio_snapshot.name,
                    base_asset_symbol=portfolio_snapshot.base_asset_symbol,
                    status=portfolio_snapshot.status,
                    aggregate_version=portfolio_snapshot.aggregate_version,
                    as_of=portfolio_snapshot.as_of,
                    lineage=_lineage(item),
                )
                continue

            if item.source_entity_type == "snapshot.paper_shadow_position":
                if item.payload.get("schema_version") != POSITION_SNAPSHOT_SCHEMA:
                    issues.append(_issue("UNSUPPORTED_SCHEMA", item, "unsupported position snapshot schema"))
                    continue
                position_snapshot = PaperShadowPositionSnapshot.model_validate(item.payload)
                if item.source_schema_version != position_snapshot.schema_version:
                    raise ValueError("position snapshot schema lineage does not match payload")
                if item.source_entity_id != position_snapshot.paper_shadow_position_id:
                    raise ValueError("position snapshot identity does not match source lineage")
                referenced_portfolio = portfolios.get(position_snapshot.paper_shadow_portfolio_id)
                if referenced_portfolio is None:
                    issues.append(
                        _issue("PORTFOLIO_MISSING", item, "position snapshot references an unknown portfolio")
                    )
                    continue
                if referenced_portfolio.mode != position_snapshot.mode:
                    issues.append(_issue("MODE_MISMATCH", item, "position and portfolio modes do not match"))
                    continue
                current_position = positions.get(position_snapshot.paper_shadow_position_id)
                if (
                    current_position is not None
                    and position_snapshot.aggregate_version <= current_position.aggregate_version
                ):
                    issues.append(
                        _issue("VERSION_CONFLICT", item, "position snapshot version is not newer than current evidence")
                    )
                    continue
                positions[position_snapshot.paper_shadow_position_id] = PaperShadowPositionProjection(
                    position_id=position_snapshot.paper_shadow_position_id,
                    portfolio_id=position_snapshot.paper_shadow_portfolio_id,
                    mode=position_snapshot.mode,
                    asset_symbol=position_snapshot.asset_symbol,
                    quantity=position_snapshot.quantity,
                    average_entry_price=position_snapshot.average_entry_price,
                    status=position_snapshot.status,
                    aggregate_version=position_snapshot.aggregate_version,
                    as_of=position_snapshot.as_of,
                    lineage=_lineage(item),
                )
                continue

            if item.source_entity_type not in {event.value for event in EVENT_PAYLOAD_SCHEMAS}:
                issues.append(_issue("UNSUPPORTED_SCHEMA", item, "unsupported Paper/Shadow source evidence type"))
                continue
            envelope = EventEnvelope.model_validate(item.payload)
            if item.source_schema_version != envelope.schema_version or item.source_entity_id != envelope.event_id:
                raise ValueError("event envelope lineage does not match immutable source evidence")
            if item.source_version != envelope.source.source_version:
                raise ValueError("event provider version does not match immutable source evidence")
            if item.source_observed_at != envelope.occurred_at:
                raise ValueError("event time does not match immutable source evidence")
            expected_payload_schema = EVENT_PAYLOAD_SCHEMAS.get(envelope.event_type)
            if expected_payload_schema != envelope.payload_schema:
                issues.append(_issue("UNSUPPORTED_SCHEMA", item, "unsupported position event payload schema"))
                continue
            payload = _payload_model(envelope)
            event_portfolio = portfolios.get(payload.portfolio_id)
            if event_portfolio is None:
                issues.append(_issue("PORTFOLIO_MISSING", item, "position event references an unknown portfolio"))
                continue
            if event_portfolio.mode != payload.mode:
                issues.append(_issue("MODE_MISMATCH", item, "position event and portfolio modes do not match"))
                continue
            event_position = positions.get(payload.position_id)
            current_version = 0 if event_position is None else event_position.aggregate_version
            if envelope.aggregate.version != current_version + 1:
                code = "VERSION_CONFLICT" if envelope.aggregate.version <= current_version else "AGGREGATE_GAP"
                issues.append(_issue(code, item, "position aggregate version is not the next contiguous version"))
                continue
            if envelope.event_type is EventType.SIMULATION_POSITION_OPENED and event_position is not None:
                issues.append(_issue("INVALID_TRANSITION", item, "position open event cannot replace existing state"))
                continue
            if envelope.event_type is not EventType.SIMULATION_POSITION_OPENED and event_position is None:
                issues.append(_issue("INVALID_TRANSITION", item, "position update or close requires existing state"))
                continue
            if event_position is not None and event_position.status == "closed":
                issues.append(_issue("INVALID_TRANSITION", item, "a closed position cannot transition again"))
                continue
            status: Literal["open", "closed"] = (
                "closed" if envelope.event_type is EventType.SIMULATION_POSITION_CLOSED else "open"
            )
            positions[payload.position_id] = PaperShadowPositionProjection(
                position_id=payload.position_id,
                portfolio_id=payload.portfolio_id,
                mode=payload.mode,
                asset_symbol=payload.asset_symbol,
                quantity=payload.quantity,
                average_entry_price=payload.average_entry_price,
                status=status,
                aggregate_version=envelope.aggregate.version,
                as_of=envelope.occurred_at,
                lineage=_lineage(item),
            )
        except (ValidationError, ValueError) as error:
            issues.append(_issue("INVALID_PAYLOAD", item, str(error)))

    ordered_portfolios = tuple(portfolios[key] for key in sorted(portfolios))
    ordered_positions = tuple(positions[key] for key in sorted(positions))
    ordered_issues = tuple(
        sorted(
            issues,
            key=lambda issue: (
                issue.code,
                "" if issue.source_entity_id is None else issue.source_entity_id,
                "" if issue.source_reference_id is None else str(issue.source_reference_id),
            ),
        )
    )
    checksum_payload = {
        "projection_version": PROJECTION_VERSION,
        "complete": not ordered_issues,
        "evidence_count": len(evidence),
        "portfolios": [item.model_dump(mode="json") for item in ordered_portfolios],
        "positions": [item.model_dump(mode="json") for item in ordered_positions],
        "issues": [item.model_dump(mode="json") for item in ordered_issues],
    }
    return PaperShadowProjectionView(
        projection_version=PROJECTION_VERSION,
        complete=not ordered_issues,
        evidence_count=len(evidence),
        portfolios=ordered_portfolios,
        positions=ordered_positions,
        issues=ordered_issues,
        projection_sha256=canonical_json_sha256(checksum_payload),
    )
