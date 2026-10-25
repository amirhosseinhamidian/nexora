from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from nexora.adapters.trd_bot import EventEnvelope, ExportManifest, SnapshotPage, TrdBotSchemaError
from nexora.adapters.trd_bot.client import TrdBotClient
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "contracts/integration/v1/fixtures"


def _fixture(name: str) -> dict[str, object]:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_event_fixture_validates_checksum_and_lineage() -> None:
    event = EventEnvelope.model_validate(_fixture("decision-event.json"))

    assert event.source.source_product == "trd_bot"
    assert event.aggregate.version == 1
    assert event.payload["mode"] == "shadow"


def test_event_checksum_mismatch_is_rejected() -> None:
    payload = _fixture("decision-event.json")
    payload["payload"] = {"decision_id": "tampered"}

    with pytest.raises(ValidationError, match="payload checksum mismatch"):
        EventEnvelope.model_validate(payload)


def test_export_manifest_requires_complete_status() -> None:
    manifest = ExportManifest.model_validate(_fixture("export-manifest.json"))
    assert manifest.completion_status == "complete"

    changed = copy.deepcopy(_fixture("export-manifest.json"))
    changed["completion_status"] = "partial"
    with pytest.raises(ValidationError):
        ExportManifest.model_validate(changed)


def test_continuing_page_requires_a_cursor() -> None:
    with pytest.raises(ValidationError, match="requires next_cursor"):
        SnapshotPage.model_validate(
            {
                "schema_version": "nexora-source-snapshot-page-v1",
                "items": [],
                "next_cursor": None,
                "has_more": True,
            }
        )


def test_client_parser_never_exposes_invalid_payload() -> None:
    with pytest.raises(TrdBotSchemaError, match="EventEnvelope"):
        TrdBotClient._parse({"schema_version": "unknown"}, EventEnvelope)
