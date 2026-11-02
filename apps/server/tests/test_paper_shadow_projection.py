from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from nexora.adapters.trd_bot.models import EventEnvelope, EventType, ResourceType
from nexora.paper_shadow_projection import (
    ProjectionSourceEvidence,
    canonical_json_sha256,
    rebuild_paper_shadow_projection,
    validate_projection_snapshot,
)
from pydantic import ValidationError

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def _evidence(
    *,
    entity_type: str,
    entity_id: str,
    schema: str,
    payload: dict[str, Any],
    source_version: str = "0.3.1:snapshot",
    reference_id: UUID | None = None,
) -> ProjectionSourceEvidence:
    return ProjectionSourceEvidence(
        source_reference_id=reference_id or uuid4(),
        source_entity_type=entity_type,
        source_entity_id=entity_id,
        source_schema_version=schema,
        source_version=source_version,
        source_observed_at=NOW,
        payload=payload,
        payload_sha256=canonical_json_sha256(payload),
    )


def _portfolio(*, mode: str = "shadow") -> ProjectionSourceEvidence:
    payload = {
        "schema_version": "trd-paper-shadow-portfolio-v1",
        "paper_shadow_portfolio_id": "portfolio-1",
        "mode": mode,
        "name": "Primary simulation",
        "base_asset_symbol": "USDT",
        "status": "active",
        "aggregate_version": 1,
        "as_of": NOW.isoformat().replace("+00:00", "Z"),
    }
    return _evidence(
        entity_type="snapshot.paper_shadow_portfolio",
        entity_id="portfolio-1",
        schema="trd-paper-shadow-portfolio-v1",
        payload=payload,
    )


def _position(*, mode: str = "shadow", quantity: object = "1.25000000") -> ProjectionSourceEvidence:
    payload = {
        "schema_version": "trd-paper-shadow-position-v1",
        "paper_shadow_position_id": "position-1",
        "paper_shadow_portfolio_id": "portfolio-1",
        "mode": mode,
        "asset_symbol": "BTC",
        "quantity": quantity,
        "average_entry_price": "62000.00",
        "status": "open",
        "aggregate_version": 1,
        "as_of": NOW.isoformat().replace("+00:00", "Z"),
    }
    return _evidence(
        entity_type="snapshot.paper_shadow_position",
        entity_id="position-1",
        schema="trd-paper-shadow-position-v1",
        payload=payload,
    )


def _event(event_type: EventType, *, version: int, quantity: str) -> ProjectionSourceEvidence:
    payload = {
        "position_id": "position-1",
        "portfolio_id": "portfolio-1",
        "mode": "shadow",
        "asset_symbol": "BTC",
        "quantity": quantity,
        "average_entry_price": "62000.00",
    }
    envelope = EventEnvelope.model_validate(
        {
            "schema_version": "trd-integration-event-envelope-v1",
            "event_id": f"evt_projection_{version:016d}",
            "event_type": event_type.value,
            "occurred_at": NOW.isoformat().replace("+00:00", "Z"),
            "emitted_at": NOW.isoformat().replace("+00:00", "Z"),
            "source": {
                "schema_version": "nexora-source-reference-v1",
                "source_product": "trd_bot",
                "source_version": "0.3.1",
                "resource_type": "paper_shadow_position",
                "resource_id": "position-1",
                "resource_schema_version": "trd-paper-shadow-position-v1",
                "observed_at": NOW.isoformat().replace("+00:00", "Z"),
                "checksum": f"sha256:{'a' * 64}",
            },
            "aggregate": {"type": "paper_shadow_position", "id": "position-1", "version": version},
            "correlation_id": str(uuid4()),
            "causation_id": None,
            "idempotency_key": f"projection-position-1-version-{version}",
            "payload_schema": {
                EventType.SIMULATION_POSITION_OPENED: "simulation-position-opened-v1",
                EventType.SIMULATION_POSITION_UPDATED: "simulation-position-updated-v1",
                EventType.SIMULATION_POSITION_CLOSED: "simulation-position-closed-v1",
            }[event_type],
            "payload": payload,
            "payload_checksum": f"sha256:{canonical_json_sha256(payload)}",
        }
    )
    encoded = envelope.model_dump(mode="json")
    return _evidence(
        entity_type=event_type.value,
        entity_id=envelope.event_id,
        schema=envelope.schema_version,
        payload=encoded,
        source_version="0.3.1",
    )


def test_projection_rebuilds_snapshot_state_with_lineage() -> None:
    result = rebuild_paper_shadow_projection((_portfolio(), _position()))

    assert result.complete is True
    assert result.evidence_count == 2
    assert result.portfolios[0].mode == "shadow"
    assert str(result.positions[0].quantity) == "1.25000000"
    assert result.positions[0].lineage.payload_sha256
    assert len(result.projection_sha256) == 64


def test_contiguous_event_updates_the_projected_position() -> None:
    updated = _event(EventType.SIMULATION_POSITION_UPDATED, version=2, quantity="1.50000000")
    result = rebuild_paper_shadow_projection((_portfolio(), _position(), updated))

    assert result.complete is True
    assert result.positions[0].aggregate_version == 2
    assert str(result.positions[0].quantity) == "1.50000000"
    assert result.positions[0].lineage.source_entity_id == updated.source_entity_id


def test_aggregate_gap_fails_closed_and_preserves_last_verified_state() -> None:
    gap = _event(EventType.SIMULATION_POSITION_UPDATED, version=3, quantity="2.00000000")
    result = rebuild_paper_shadow_projection((_portfolio(), _position(), gap))

    assert result.complete is False
    assert result.positions[0].aggregate_version == 1
    assert [issue.code for issue in result.issues] == ["AGGREGATE_GAP"]


def test_mode_mismatch_is_visible_and_position_is_not_projected() -> None:
    result = rebuild_paper_shadow_projection((_portfolio(mode="paper"), _position(mode="shadow")))

    assert result.complete is False
    assert result.positions == ()
    assert result.issues[0].code == "MODE_MISMATCH"


def test_checksum_mismatch_is_visible() -> None:
    position = _position().model_copy(update={"payload_sha256": "0" * 64})
    result = rebuild_paper_shadow_projection((_portfolio(), position))

    assert result.complete is False
    assert result.issues[0].code == "CHECKSUM_MISMATCH"


def test_projection_checksum_is_independent_of_input_order() -> None:
    portfolio = _portfolio()
    position = _position()
    first = rebuild_paper_shadow_projection((portfolio, position))
    second = rebuild_paper_shadow_projection((position, portfolio))

    assert first == second


def test_same_timestamp_events_are_applied_in_aggregate_version_order() -> None:
    updated = _event(EventType.SIMULATION_POSITION_UPDATED, version=2, quantity="1.50000000")
    closed = _event(EventType.SIMULATION_POSITION_CLOSED, version=3, quantity="0")
    result = rebuild_paper_shadow_projection((_portfolio(), closed, _position(), updated))

    assert result.complete is True
    assert result.positions[0].status == "closed"
    assert result.positions[0].aggregate_version == 3


def test_projection_snapshot_rejects_binary_numeric_values() -> None:
    with pytest.raises(ValidationError, match="decimal values must be encoded as strings"):
        validate_projection_snapshot(ResourceType.PAPER_SHADOW_POSITION, _position(quantity=1.25).payload)


def test_projection_snapshot_rejects_live_mode() -> None:
    with pytest.raises(ValidationError, match=r"paper.*shadow"):
        validate_projection_snapshot(ResourceType.PAPER_SHADOW_PORTFOLIO, _portfolio(mode="live").payload)
