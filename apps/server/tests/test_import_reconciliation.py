from __future__ import annotations

import json
from uuid import uuid4

import pytest
from nexora.import_reconciliation import (
    ImportFormat,
    ImportValidationError,
    NormalizedImportRow,
    RejectedImportRow,
    normalize_import,
)


def _row(*, row_id: str = "row-1", quantity: str = "10") -> dict[str, object]:
    asset_id = uuid4()
    return {
        "row_id": row_id,
        "portfolio_id": str(uuid4()),
        "transaction_kind": "opening_balance",
        "occurred_at": "2026-10-31T12:00:00Z",
        "memo": "Imported opening balance",
        "legs": [
            {"account_id": str(uuid4()), "asset_id": str(asset_id), "quantity": quantity},
            {"external_counterparty": "Opening equity", "asset_id": str(asset_id), "quantity": f"-{quantity}"},
        ],
    }


def test_nexora_json_normalization_is_deterministic_and_exact_decimal() -> None:
    content = json.dumps({"schema_version": "nexora-transaction-import-v1", "rows": [_row()]})
    first = normalize_import(ImportFormat.NEXORA_JSON, content)
    second = normalize_import(ImportFormat.NEXORA_JSON, content)
    assert first.content_sha256 == second.content_sha256
    assert first.rows == second.rows
    assert isinstance(first.rows[0], NormalizedImportRow)
    assert first.rows[0].canonical_payload["legs"][0]["quantity"] == "10"


def test_invalid_and_duplicate_rows_are_quarantined_without_aborting_preview() -> None:
    valid = _row()
    invalid = _row(row_id="bad", quantity="9")
    invalid_legs = invalid["legs"]
    assert isinstance(invalid_legs, list)
    assert isinstance(invalid_legs[1], dict)
    invalid_legs[1]["quantity"] = "-8"
    content = json.dumps({"schema_version": "nexora-transaction-import-v1", "rows": [valid, valid, invalid]})
    preview = normalize_import(ImportFormat.NEXORA_JSON, content)
    assert isinstance(preview.rows[0], NormalizedImportRow)
    assert isinstance(preview.rows[1], RejectedImportRow)
    assert preview.rows[1].reason_code == "DUPLICATE_WITHIN_BATCH"
    assert isinstance(preview.rows[2], RejectedImportRow)
    assert preview.rows[2].reason_code == "ROW_VALIDATION_FAILED"


def test_csv_header_and_json_schema_are_fail_closed() -> None:
    with pytest.raises(ImportValidationError, match="header"):
        normalize_import(ImportFormat.CSV, "portfolio_id,row_id\na,b\n")
    with pytest.raises(ImportValidationError, match="schema version"):
        normalize_import(ImportFormat.NEXORA_JSON, '{"schema_version":"unknown","rows":[]}')


def test_unknown_fields_never_enter_normalized_evidence() -> None:
    row = _row()
    row["api_key"] = "forbidden"
    content = json.dumps({"schema_version": "nexora-transaction-import-v1", "rows": [row]})
    preview = normalize_import(ImportFormat.NEXORA_JSON, content)
    assert isinstance(preview.rows[0], RejectedImportRow)
    assert "unknown fields" in preview.rows[0].detail
