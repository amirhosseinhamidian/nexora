from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from nexora.transaction_journal import (
    JournalValidationError,
    TransactionKind,
    TransactionLegInput,
    canonical_quantity,
    normalize_optional_text,
    normalize_quantity,
    validate_balanced_legs,
)

MAX_IMPORT_BYTES = 1_048_576
MAX_IMPORT_ROWS = 5_000


class ImportFormat(StrEnum):
    CSV = "csv"
    NEXORA_JSON = "nexora_json"


class ImportBatchStatus(StrEnum):
    DRY_RUN = "dry_run"
    REVIEWED = "reviewed"
    PUBLISHED = "published"
    QUARANTINED = "quarantined"


class ImportRowStatus(StrEnum):
    READY = "ready"
    DUPLICATE = "duplicate"
    QUARANTINED = "quarantined"
    PUBLISHED = "published"


class ReconciliationState(StrEnum):
    OPEN = "open"
    MATCHED = "matched"
    ACCEPTED_DIFFERENCE = "accepted_difference"
    RESOLVED = "resolved"
    IGNORED_WITH_REASON = "ignored_with_reason"


class ImportReconciliationError(RuntimeError):
    """Base error for bounded import and reconciliation operations."""


class ImportValidationError(ImportReconciliationError):
    """The import document or requested transition is invalid."""


class ImportConflict(ImportReconciliationError):
    """The import batch or reconciliation state changed concurrently."""


class ImportNotFound(ImportReconciliationError):
    """The requested owner-scoped import evidence does not exist."""


@dataclass(frozen=True, slots=True)
class NormalizedImportRow:
    row_number: int
    external_row_id: str
    portfolio_id: UUID
    transaction_kind: TransactionKind
    occurred_at: datetime
    memo: str | None
    legs: tuple[TransactionLegInput, ...]
    canonical_payload: dict[str, Any]
    fingerprint_sha256: str


@dataclass(frozen=True, slots=True)
class RejectedImportRow:
    row_number: int
    external_row_id: str | None
    reason_code: str
    detail: str


@dataclass(frozen=True, slots=True)
class ImportPreview:
    source_format: ImportFormat
    content_sha256: str
    rows: tuple[NormalizedImportRow | RejectedImportRow, ...]


@dataclass(frozen=True, slots=True)
class ImportRowView:
    import_row_id: UUID
    row_number: int
    external_row_id: str | None
    fingerprint_sha256: str | None
    status: ImportRowStatus
    reason_code: str | None
    normalized_payload: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class ImportBatchView:
    import_batch_id: UUID
    source_format: ImportFormat
    content_sha256: str
    status: ImportBatchStatus
    row_count: int
    ready_count: int
    duplicate_count: int
    quarantined_count: int
    review_reason: str | None
    created_at: datetime
    reviewed_at: datetime | None
    published_at: datetime | None
    rows: tuple[ImportRowView, ...]


@dataclass(frozen=True, slots=True)
class ReconciliationCaseView:
    reconciliation_case_id: UUID
    import_batch_id: UUID
    import_row_id: UUID
    transaction_id: UUID | None
    state: ReconciliationState
    difference_code: str
    reason: str | None
    row_version: int
    created_at: datetime
    updated_at: datetime


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _aware_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ImportValidationError("occurred_at must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ImportValidationError("occurred_at must include a UTC offset")
    return parsed.astimezone(UTC)


def _string(value: Any, *, field: str, maximum: int, minimum: int = 1) -> str:
    if not isinstance(value, str):
        raise ImportValidationError(f"{field} must be a string")
    normalized = " ".join(value.split())
    if not minimum <= len(normalized) <= maximum:
        raise ImportValidationError(f"{field} must contain {minimum}-{maximum} characters")
    return normalized


def _normalize_row(raw: dict[str, Any], row_number: int) -> NormalizedImportRow:
    allowed = {"row_id", "portfolio_id", "transaction_kind", "occurred_at", "memo", "legs"}
    unknown = set(raw) - allowed
    if unknown:
        raise ImportValidationError(f"unknown fields: {', '.join(sorted(unknown))}")
    external_row_id = _string(raw.get("row_id"), field="row_id", maximum=160)
    try:
        portfolio_id = UUID(_string(raw.get("portfolio_id"), field="portfolio_id", maximum=36))
        transaction_kind = TransactionKind(_string(raw.get("transaction_kind"), field="transaction_kind", maximum=24))
    except ValueError as error:
        raise ImportValidationError("portfolio_id or transaction_kind is invalid") from error
    occurred_at = _aware_utc(_string(raw.get("occurred_at"), field="occurred_at", maximum=40))
    memo_value = raw.get("memo")
    memo = normalize_optional_text(memo_value, field="memo", maximum=500) if memo_value not in (None, "") else None
    raw_legs = raw.get("legs")
    if not isinstance(raw_legs, list) or not 2 <= len(raw_legs) <= 64:
        raise ImportValidationError("legs must contain 2-64 objects")
    legs: list[TransactionLegInput] = []
    canonical_legs: list[dict[str, Any]] = []
    for raw_leg in raw_legs:
        if not isinstance(raw_leg, dict):
            raise ImportValidationError("each leg must be an object")
        leg_unknown = set(raw_leg) - {"account_id", "external_counterparty", "asset_id", "quantity", "memo"}
        if leg_unknown:
            raise ImportValidationError(f"unknown leg fields: {', '.join(sorted(leg_unknown))}")
        account_raw = raw_leg.get("account_id")
        external_raw = raw_leg.get("external_counterparty")
        if (account_raw is None) == (external_raw is None):
            raise ImportValidationError("each leg requires exactly one account_id or external_counterparty")
        try:
            account_id = UUID(account_raw) if isinstance(account_raw, str) else None
            asset_id = UUID(_string(raw_leg.get("asset_id"), field="asset_id", maximum=36))
            quantity = normalize_quantity(_string(raw_leg.get("quantity"), field="quantity", maximum=92))
        except (ValueError, JournalValidationError) as error:
            raise ImportValidationError(str(error)) from error
        external = (
            _string(external_raw, field="external_counterparty", maximum=160) if external_raw is not None else None
        )
        leg_memo_raw = raw_leg.get("memo")
        leg_memo = (
            normalize_optional_text(leg_memo_raw, field="leg memo", maximum=240)
            if leg_memo_raw not in (None, "")
            else None
        )
        leg = TransactionLegInput(
            account_id=account_id,
            external_counterparty=external,
            asset_id=asset_id,
            quantity=quantity,
            memo=leg_memo,
        )
        legs.append(leg)
        canonical_legs.append(
            {
                "account_id": str(account_id) if account_id is not None else None,
                "external_counterparty": external,
                "asset_id": str(asset_id),
                "quantity": canonical_quantity(quantity),
                "memo": leg_memo,
            }
        )
    try:
        validate_balanced_legs(tuple(legs))
    except JournalValidationError as error:
        raise ImportValidationError(str(error)) from error
    payload = {
        "schema_version": "nexora-normalized-import-row-v1",
        "row_id": external_row_id,
        "portfolio_id": str(portfolio_id),
        "transaction_kind": transaction_kind.value,
        "occurred_at": occurred_at.isoformat().replace("+00:00", "Z"),
        "memo": memo,
        "legs": canonical_legs,
    }
    return NormalizedImportRow(
        row_number=row_number,
        external_row_id=external_row_id,
        portfolio_id=portfolio_id,
        transaction_kind=transaction_kind,
        occurred_at=occurred_at,
        memo=memo,
        legs=tuple(legs),
        canonical_payload=payload,
        fingerprint_sha256=_canonical_sha256(payload),
    )


def _csv_rows(content: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(content, newline=""))
    expected = ["row_id", "portfolio_id", "transaction_kind", "occurred_at", "memo", "legs"]
    if reader.fieldnames != expected:
        raise ImportValidationError("CSV header does not match the frozen import schema")
    rows: list[dict[str, Any]] = []
    for row in reader:
        try:
            legs = json.loads(row["legs"])
        except (TypeError, json.JSONDecodeError) as error:
            legs = None
            row["_parse_error"] = str(error)
        rows.append({**row, "legs": legs})
    return rows


def _json_rows(content: str) -> list[dict[str, Any]]:
    try:
        document = json.loads(content)
    except json.JSONDecodeError as error:
        raise ImportValidationError("Nexora JSON document is invalid") from error
    if not isinstance(document, dict) or set(document) != {"schema_version", "rows"}:
        raise ImportValidationError("Nexora JSON root must contain only schema_version and rows")
    if document.get("schema_version") != "nexora-transaction-import-v1":
        raise ImportValidationError("Nexora JSON schema version is unsupported")
    rows = document.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ImportValidationError("Nexora JSON rows must be an array of objects")
    return rows


def normalize_import(source_format: ImportFormat, content: str) -> ImportPreview:
    encoded = content.encode("utf-8")
    if not encoded or len(encoded) > MAX_IMPORT_BYTES:
        raise ImportValidationError("import content must contain 1-1048576 UTF-8 bytes")
    rows = _csv_rows(content) if source_format is ImportFormat.CSV else _json_rows(content)
    if not 1 <= len(rows) <= MAX_IMPORT_ROWS:
        raise ImportValidationError("import must contain 1-5000 rows")
    normalized: list[NormalizedImportRow | RejectedImportRow] = []
    seen: set[str] = set()
    for row_number, raw in enumerate(rows, start=1):
        try:
            row = _normalize_row(raw, row_number)
        except (ImportValidationError, JournalValidationError) as error:
            external = raw.get("row_id") if isinstance(raw.get("row_id"), str) else None
            normalized.append(RejectedImportRow(row_number, external, "ROW_VALIDATION_FAILED", str(error)))
            continue
        if row.fingerprint_sha256 in seen:
            normalized.append(
                RejectedImportRow(row_number, row.external_row_id, "DUPLICATE_WITHIN_BATCH", "duplicate row")
            )
            continue
        seen.add(row.fingerprint_sha256)
        normalized.append(row)
    return ImportPreview(source_format, content_sha256(content), tuple(normalized))


def restore_normalized_row(payload: dict[str, Any], row_number: int) -> NormalizedImportRow:
    if payload.get("schema_version") != "nexora-normalized-import-row-v1":
        raise ImportValidationError("normalized import row schema is unsupported")
    raw = {key: value for key, value in payload.items() if key != "schema_version"}
    return _normalize_row(raw, row_number)


def normalize_decision_reason(value: str | None, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise ImportValidationError("an owner-supplied reason is required")
        return None
    normalized = " ".join(value.split())
    if not 8 <= len(normalized) <= 500:
        raise ImportValidationError("reason must contain 8-500 characters")
    return normalized
