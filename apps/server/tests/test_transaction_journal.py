from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from nexora.transaction_contracts import CreateTransactionRequest
from nexora.transaction_journal import (
    JournalValidationError,
    TransactionLegInput,
    canonical_quantity,
    normalize_idempotency_key,
    normalize_quantity,
    validate_balanced_legs,
)
from pydantic import ValidationError


def test_decimal_quantity_is_plain_exact_and_canonical() -> None:
    assert normalize_quantity("123.4500") == Decimal("123.4500")
    assert canonical_quantity(Decimal("123.4500")) == "123.45"
    for invalid in ("0", "1e-8", "+1", "NaN", "Infinity", " 1.0"):
        with pytest.raises(JournalValidationError):
            normalize_quantity(invalid)


def test_balanced_legs_require_zero_sum_per_asset_and_an_owner_account() -> None:
    asset_id = uuid4()
    account_id = uuid4()
    validate_balanced_legs(
        (
            TransactionLegInput(asset_id=asset_id, account_id=account_id, quantity=Decimal("10")),
            TransactionLegInput(asset_id=asset_id, external_counterparty="Opening equity", quantity=Decimal("-10")),
        )
    )
    with pytest.raises(JournalValidationError, match="balance"):
        validate_balanced_legs(
            (
                TransactionLegInput(asset_id=asset_id, account_id=account_id, quantity=Decimal("10")),
                TransactionLegInput(asset_id=asset_id, external_counterparty="Opening equity", quantity=Decimal("-9")),
            )
        )


def test_idempotency_key_is_bounded_and_contains_no_whitespace() -> None:
    assert normalize_idempotency_key("manual-20261031-0001") == "manual-20261031-0001"
    for invalid in ("short", "manual key with space", "x" * 161):
        with pytest.raises(JournalValidationError):
            normalize_idempotency_key(invalid)


def test_transaction_contract_rejects_owner_override_float_and_secret_fields() -> None:
    payload = {
        "portfolio_id": str(uuid4()),
        "transaction_kind": "opening_balance",
        "occurred_at": "2026-10-31T12:00:00Z",
        "source_kind": "manual",
        "source_reference": "manual-entry-1",
        "source_payload_sha256": "a" * 64,
        "owner_id": str(uuid4()),
        "api_key": "forbidden",
        "legs": [
            {
                "account_id": str(uuid4()),
                "asset_id": str(uuid4()),
                "quantity": 10.5,
            },
            {
                "external_counterparty": "Opening equity",
                "asset_id": str(uuid4()),
                "quantity": "-10.5",
            },
        ],
    }
    with pytest.raises(ValidationError) as error:
        CreateTransactionRequest.model_validate(payload)
    locations = {item["loc"] for item in error.value.errors()}
    assert ("owner_id",) in locations
    assert ("api_key",) in locations
    assert ("legs", 0, "quantity") in locations
