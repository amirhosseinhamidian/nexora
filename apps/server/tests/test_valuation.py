from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from nexora.valuation import (
    ValuationEvidenceState,
    ValuationValidationError,
    aware_utc,
    canonical_decimal,
    canonical_request_sha256,
    evidence_state,
    normalize_positive_decimal,
    normalize_reference,
    normalize_sha256,
)


def test_exact_decimal_normalization_and_canonical_encoding() -> None:
    assert normalize_positive_decimal("120.5000") == Decimal("120.5000")
    assert canonical_decimal(Decimal("120.5000")) == "120.5"
    with pytest.raises(ValuationValidationError, match="binary floating"):
        normalize_positive_decimal(1.25)  # type: ignore[arg-type]
    for invalid in ("0", "-1", "NaN", "Infinity", "0.0000000000000000000000000000001"):
        with pytest.raises(ValuationValidationError):
            normalize_positive_decimal(invalid)
    for overflow in ("1" * 31, "1e30"):
        with pytest.raises(ValuationValidationError, match="supported precision"):
            normalize_positive_decimal(overflow)


def test_timestamps_require_offsets_and_staleness_is_explicit() -> None:
    observed = datetime(2026, 11, 1, 8, tzinfo=UTC)
    valid_until = observed + timedelta(minutes=5)
    assert aware_utc(observed) == observed
    assert evidence_state(as_of=valid_until, valid_until=valid_until) is ValuationEvidenceState.FRESH
    assert (
        evidence_state(as_of=valid_until + timedelta(microseconds=1), valid_until=valid_until)
        is ValuationEvidenceState.STALE
    )
    assert evidence_state(as_of=observed, valid_until=None, present=False) is ValuationEvidenceState.MISSING
    with pytest.raises(ValuationValidationError, match="UTC offset"):
        aware_utc(datetime(2026, 11, 1, 8))


def test_manual_reason_and_canonical_checksum_are_deterministic() -> None:
    assert normalize_reference("  owner   supplied reason  ", field="reason", minimum=8, maximum=500) == (
        "owner supplied reason"
    )
    with pytest.raises(ValuationValidationError, match="8-500"):
        normalize_reference("short", field="reason", minimum=8, maximum=500)
    first = canonical_request_sha256({"value": "1.2", "asset": "BTC"})
    second = canonical_request_sha256({"asset": "BTC", "value": "1.2"})
    assert first == second


def test_source_payload_checksum_requires_canonical_lowercase_sha256() -> None:
    assert normalize_sha256("a" * 64, field="payload") == "a" * 64
    for invalid in ("A" * 64, "a" * 63, "not-a-checksum"):
        with pytest.raises(ValuationValidationError, match="lowercase SHA-256"):
            normalize_sha256(invalid, field="payload")
