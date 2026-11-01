from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from uuid import UUID


class ValuationEvidenceKind(StrEnum):
    PRICE_OBSERVATION = "price_observation"
    FX_RATE_OBSERVATION = "fx_rate_observation"
    MANUAL_VALUATION = "manual_valuation"
    BASE_ASSET_IDENTITY = "base_asset_identity"
    NONE = "none"


class ValuationEvidenceState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"


class ValuationSourceKind(StrEnum):
    PROVIDER = "provider"
    IMPORT = "import"


class ValuationError(RuntimeError):
    """Base error for valuation evidence operations."""


class ValuationNotFound(ValuationError):
    """An owner-scoped valuation resource is unavailable."""


class ValuationConflict(ValuationError):
    """An idempotency key conflicts with immutable evidence."""


class ValuationValidationError(ValuationError):
    """Valuation evidence violates a fail-closed domain invariant."""


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValuationValidationError("valuation timestamps must include a UTC offset")
    return value.astimezone(UTC)


def normalize_positive_decimal(value: str | Decimal) -> Decimal:
    if isinstance(value, (float, bool)):
        raise ValuationValidationError("binary floating point is forbidden")
    try:
        normalized = Decimal(value) if isinstance(value, str) else value
    except (InvalidOperation, ValueError) as error:
        raise ValuationValidationError("valuation amount is invalid") from error
    if not normalized.is_finite() or normalized <= 0:
        raise ValuationValidationError("valuation amount must be finite and positive")
    exponent = normalized.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValuationValidationError("valuation amount exceeds supported precision")
    integer_digits = max(normalized.adjusted() + 1, 0)
    scale = max(-exponent, 0)
    if integer_digits > 30 or scale > 30:
        raise ValuationValidationError("valuation amount exceeds supported precision")
    return normalized


def normalize_sha256(value: str, *, field: str) -> str:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValuationValidationError(f"{field} must be a lowercase SHA-256 digest")
    return value


def canonical_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    rendered = format(normalized, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"-0", ""} else rendered


def normalize_reference(value: str, *, field: str, minimum: int = 1, maximum: int = 160) -> str:
    normalized = " ".join(value.split())
    if not minimum <= len(normalized) <= maximum:
        raise ValuationValidationError(f"{field} must contain {minimum}-{maximum} characters")
    return normalized


def canonical_request_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def evidence_state(*, as_of: datetime, valid_until: datetime | None, present: bool = True) -> ValuationEvidenceState:
    resolved_as_of = aware_utc(as_of)
    if not present:
        return ValuationEvidenceState.MISSING
    if valid_until is None or resolved_as_of <= aware_utc(valid_until):
        return ValuationEvidenceState.FRESH
    return ValuationEvidenceState.STALE


@dataclass(frozen=True, slots=True)
class PriceObservationView:
    price_observation_id: UUID
    asset_id: UUID
    quote_asset_id: UUID
    price: Decimal
    observed_at: datetime
    valid_until: datetime
    source_kind: ValuationSourceKind
    source_reference: str
    source_payload_sha256: str
    idempotency_key: str
    request_sha256: str
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class FxRateObservationView:
    fx_rate_observation_id: UUID
    base_asset_id: UUID
    quote_asset_id: UUID
    rate: Decimal
    observed_at: datetime
    valid_until: datetime
    source_kind: ValuationSourceKind
    source_reference: str
    source_payload_sha256: str
    idempotency_key: str
    request_sha256: str
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class ManualValuationView:
    manual_valuation_id: UUID
    portfolio_id: UUID
    asset_id: UUID
    quote_asset_id: UUID
    unit_value: Decimal
    valued_at: datetime
    valid_until: datetime
    reason: str
    source_reference: str
    source_payload_sha256: str
    idempotency_key: str
    request_sha256: str
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class ValuationStatusView:
    asset_id: UUID
    quote_asset_id: UUID
    as_of: datetime
    state: ValuationEvidenceState
    evidence_kind: ValuationEvidenceKind
    unit_value: Decimal | None
    evidence_id: UUID | None
    evidence_at: datetime | None
    valid_until: datetime | None
    source_reference: str | None
