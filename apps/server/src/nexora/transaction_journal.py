from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

DECIMAL_PATTERN = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class TransactionKind(StrEnum):
    BUY = "buy"
    SELL = "sell"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    FEE = "fee"
    INCOME = "income"
    REWARD = "reward"
    AIRDROP = "airdrop"
    ADJUSTMENT = "adjustment"
    OPENING_BALANCE = "opening_balance"


class JournalSourceKind(StrEnum):
    MANUAL = "manual"
    IMPORT = "import"
    TRD_BOT = "trd_bot"


class CorrectionKind(StrEnum):
    REVERSAL = "reversal"
    SUPERSESSION = "supersession"


class TransactionJournalError(RuntimeError):
    """Base error for immutable owner-scoped transaction journal operations."""


class JournalNotFound(TransactionJournalError):
    """The requested owner-scoped journal record does not exist."""


class JournalConflict(TransactionJournalError):
    """An idempotency, correction, concurrency, or journal invariant failed."""


class JournalValidationError(TransactionJournalError):
    """The proposed transaction is not a valid balanced journal entry."""


def normalize_idempotency_key(value: str) -> str:
    normalized = value.strip()
    if not 16 <= len(normalized) <= 160 or any(character.isspace() for character in normalized):
        raise JournalValidationError("idempotency key must contain 16-160 non-whitespace characters")
    return normalized


def normalize_source_reference(value: str) -> str:
    normalized = value.strip()
    if not 1 <= len(normalized) <= 160 or any(ord(character) < 32 for character in normalized):
        raise JournalValidationError("source reference must contain 1-160 visible characters")
    return normalized


def normalize_optional_text(value: str | None, *, field: str, maximum: int, minimum: int = 1) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if not minimum <= len(normalized) <= maximum:
        raise JournalValidationError(f"{field} must contain {minimum}-{maximum} characters")
    return normalized


def normalize_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if SHA256_PATTERN.fullmatch(normalized) is None:
        raise JournalValidationError("source payload checksum must be lowercase SHA-256")
    return normalized


def normalize_quantity(value: str) -> Decimal:
    if DECIMAL_PATTERN.fullmatch(value) is None:
        raise JournalValidationError("quantity must be a plain signed decimal string")
    try:
        quantity = Decimal(value)
    except InvalidOperation as error:
        raise JournalValidationError("quantity must be a finite decimal") from error
    if not quantity.is_finite() or quantity == 0:
        raise JournalValidationError("quantity must be finite and non-zero")
    digits = quantity.as_tuple().digits
    exponent = quantity.as_tuple().exponent
    if not isinstance(exponent, int):
        raise JournalValidationError("quantity must be a finite decimal")
    scale = max(0, -exponent)
    if len(digits) > 60 or scale > 30:
        raise JournalValidationError("quantity exceeds the 60-digit or 30-decimal-place boundary")
    return quantity


def canonical_quantity(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered == "-0" else rendered


def decimal_scale(value: Decimal) -> int:
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise JournalValidationError("quantity must be a finite decimal")
    return max(0, -exponent)


@dataclass(frozen=True, slots=True)
class TransactionLegInput:
    asset_id: UUID
    quantity: Decimal
    account_id: UUID | None = None
    external_counterparty: str | None = None
    memo: str | None = None


@dataclass(frozen=True, slots=True)
class TransactionLegView:
    transaction_leg_id: UUID
    sequence: int
    account_id: UUID | None
    external_counterparty: str | None
    asset_id: UUID
    quantity: Decimal
    memo: str | None


@dataclass(frozen=True, slots=True)
class TransactionView:
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
    legs: tuple[TransactionLegView, ...]


def validate_balanced_legs(legs: tuple[TransactionLegInput, ...]) -> None:
    if len(legs) < 2:
        raise JournalValidationError("a posted transaction requires at least two legs")
    if not any(leg.account_id is not None for leg in legs):
        raise JournalValidationError("a transaction requires at least one owner account leg")
    balances: dict[UUID, Decimal] = {}
    for leg in legs:
        if (leg.account_id is None) == (leg.external_counterparty is None):
            raise JournalValidationError("each leg requires exactly one account or external counterparty")
        balances[leg.asset_id] = balances.get(leg.asset_id, Decimal(0)) + leg.quantity
    if any(balance != 0 for balance in balances.values()):
        raise JournalValidationError("transaction legs must balance to zero for every asset")
