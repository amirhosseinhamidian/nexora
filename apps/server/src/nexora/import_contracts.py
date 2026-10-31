from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nexora.import_reconciliation import (
    ImportBatchStatus,
    ImportFormat,
    ImportRowStatus,
    ReconciliationState,
)


class ImportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ImportDryRunRequest(ImportModel):
    source_format: ImportFormat
    content: str = Field(min_length=1, max_length=1_048_576)


class ImportReviewRequest(ImportModel):
    reason: str = Field(min_length=8, max_length=500)


class ReconciliationDecisionRequest(ImportModel):
    state: ReconciliationState
    expected_row_version: int = Field(ge=1)
    reason: str | None = Field(default=None, min_length=8, max_length=500)


class ImportRowResponse(ImportModel):
    schema_version: Literal["nexora-import-row-v1"] = "nexora-import-row-v1"
    import_row_id: UUID
    row_number: int
    external_row_id: str | None
    fingerprint_sha256: str | None
    status: ImportRowStatus
    reason_code: str | None
    normalized_payload: dict[str, object] | None


class ImportBatchResponse(ImportModel):
    schema_version: Literal["nexora-import-batch-v1"] = "nexora-import-batch-v1"
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
    rows: list[ImportRowResponse]


class ImportBatchListResponse(ImportModel):
    schema_version: Literal["nexora-import-batch-list-v1"] = "nexora-import-batch-list-v1"
    items: list[ImportBatchResponse]


class ReconciliationCaseResponse(ImportModel):
    schema_version: Literal["nexora-reconciliation-case-v1"] = "nexora-reconciliation-case-v1"
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


class ReconciliationCaseListResponse(ImportModel):
    schema_version: Literal["nexora-reconciliation-case-list-v1"] = "nexora-reconciliation-case-list-v1"
    items: list[ReconciliationCaseResponse]
