from __future__ import annotations

from datetime import timedelta

import pytest
from nexora.adapters.postgresql.durable import canonical_payload_sha256, retry_delay


def test_canonical_payload_checksum_is_order_independent() -> None:
    assert canonical_payload_sha256({"b": 2, "a": 1}) == canonical_payload_sha256({"a": 1, "b": 2})


def test_retry_delay_is_exponential_and_bounded() -> None:
    assert retry_delay(1) == timedelta(seconds=1)
    assert retry_delay(4) == timedelta(seconds=8)
    assert retry_delay(20) == timedelta(seconds=300)
    with pytest.raises(ValueError, match="positive"):
        retry_delay(0)
