from __future__ import annotations

import pytest
from nexora.portfolio_contracts import CreateAccountRequest
from nexora.portfolio_registry import (
    normalize_asset_symbol,
    normalize_identifier,
    normalize_name,
    normalize_registry_key,
)
from pydantic import ValidationError


def test_registry_normalization_is_deterministic_and_bounded() -> None:
    assert normalize_registry_key(" core-usd ") == "core-usd"
    assert normalize_asset_symbol(" btc ") == "BTC"
    assert normalize_name("  Main   Portfolio  ") == "Main Portfolio"
    assert normalize_identifier("BTC-USD") == "BTC-USD"


@pytest.mark.parametrize("value", ["", "has space", "../escape", "a" * 81])
def test_registry_keys_reject_ambiguous_or_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_registry_key(value)


def test_account_contract_rejects_credentials_and_owner_override() -> None:
    payload = {
        "portfolio_id": "d23455ee-e8c6-4bea-89f0-042eb16b77f9",
        "account_key": "watch-only",
        "name": "Watch only",
        "kind": "wallet_watch_only",
        "owner_id": "d238d14b-3e3f-41ca-9e21-adf20da45c01",
        "private_key": "must-never-enter-nexora",
    }
    with pytest.raises(ValidationError) as error:
        CreateAccountRequest.model_validate(payload)
    assert {item["loc"] for item in error.value.errors()} == {("owner_id",), ("private_key",)}
