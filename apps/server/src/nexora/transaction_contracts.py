from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nexora.transaction_journal import CorrectionKind, JournalSourceKind, TransactionKind


class JournalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class TransactionLegRequest(JournalModel):
    account_id: UUID | None = None
    external_counterparty: str | None = Field(default=None, min_length=1, max_length=160)
    asset_id: UUID
    quantity: str = Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$", max_length=92)
    memo: str | None = Field(default=None, min_length=1, max_length=240)

    @model_validator(mode="after")
    def exactly_one_account_boundary(self) -> TransactionLegRequest:
        if (self.account_id is None) == (self.external_counterparty is None):
            raise ValueError("exactly one account_id or external_counterparty is required")
        return self


class SourceLineageRequest(JournalModel):
    source_kind: JournalSourceKind
    source_reference: str = Field(min_length=1, max_length=160)
    source_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CreateTransactionRequest(SourceLineageRequest):
    portfolio_id: UUID
    transaction_kind: TransactionKind
    occurred_at: datetime
    memo: str | None = Field(default=None, min_length=1, max_length=500)
    legs: list[TransactionLegRequest] = Field(min_length=2, max_length=64)


class ReverseTransactionRequest(SourceLineageRequest):
    occurred_at: datetime
    reason: str = Field(min_length=8, max_length=500)
    memo: str | None = Field(default=None, min_length=1, max_length=500)


class SupersedeTransactionRequest(SourceLineageRequest):
    transaction_kind: TransactionKind
    occurred_at: datetime
    reason: str = Field(min_length=8, max_length=500)
    memo: str | None = Field(default=None, min_length=1, max_length=500)
    legs: list[TransactionLegRequest] = Field(min_length=2, max_length=64)


class TransactionLegResponse(JournalModel):
    schema_version: Literal["nexora-transaction-leg-v1"] = "nexora-transaction-leg-v1"
    transaction_leg_id: UUID
    sequence: int
    account_id: UUID | None
    external_counterparty: str | None
    asset_id: UUID
    quantity: str
    memo: str | None


class TransactionResponse(JournalModel):
    schema_version: Literal["nexora-transaction-journal-v1"] = "nexora-transaction-journal-v1"
    transaction_id: UUID
    portfolio_id: UUID
    transaction_kind: TransactionKind
    idempotency_key: str
    occurred_at: datetime
    recorded_at: datetime
    source_kind: JournalSourceKind
    source_reference: str
    source_payload_sha256: str
    request_sha256: str
    memo: str | None
    correction_of_transaction_id: UUID | None
    correction_kind: CorrectionKind | None
    correction_reason: str | None
    legs: list[TransactionLegResponse]


class TransactionListResponse(JournalModel):
    schema_version: Literal["nexora-transaction-journal-list-v1"] = "nexora-transaction-journal-list-v1"
    items: list[TransactionResponse]
