from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

REGISTRY_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
ASSET_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,23}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")


class PortfolioKind(StrEnum):
    PERSONAL = "personal"
    PAPER = "paper"
    SHADOW = "shadow"


class AssetClass(StrEnum):
    CRYPTO = "crypto"
    FIAT = "fiat"
    EQUITY = "equity"
    FUND = "fund"
    COMMODITY = "commodity"
    OTHER = "other"


class AssetIdentifierScheme(StrEnum):
    ISO_4217 = "iso_4217"
    TICKER = "ticker"
    COINGECKO = "coingecko"
    ISIN = "isin"
    CUSIP = "cusip"
    FIGI = "figi"
    MANUAL = "manual"


class AccountKind(StrEnum):
    EXCHANGE = "exchange"
    WALLET_WATCH_ONLY = "wallet_watch_only"
    CASH = "cash"
    BROKERAGE_MANUAL = "brokerage_manual"
    PAPER = "paper"
    SHADOW = "shadow"
    OTHER_MANUAL = "other_manual"


class RegistryStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    INACTIVE = "inactive"
    CLOSED = "closed"


class PortfolioRegistryError(RuntimeError):
    """Base error for the owner-scoped portfolio registry."""


class RegistryNotFound(PortfolioRegistryError):
    """The requested owner-scoped registry record does not exist."""


class RegistryConflict(PortfolioRegistryError):
    """A uniqueness, lifecycle, or optimistic-concurrency invariant failed."""


def normalize_registry_key(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) > 80 or REGISTRY_KEY_PATTERN.fullmatch(normalized) is None:
        raise ValueError("registry key must be 1-80 lowercase slug characters")
    return normalized


def normalize_name(value: str) -> str:
    normalized = " ".join(value.split())
    if not 1 <= len(normalized) <= 120:
        raise ValueError("name must contain 1-120 characters")
    return normalized


def normalize_asset_symbol(value: str) -> str:
    normalized = value.strip().upper()
    if ASSET_SYMBOL_PATTERN.fullmatch(normalized) is None:
        raise ValueError("asset symbol is invalid")
    return normalized


def normalize_identifier(value: str) -> str:
    normalized = value.strip()
    if IDENTIFIER_PATTERN.fullmatch(normalized) is None:
        raise ValueError("asset identifier is invalid")
    return normalized


@dataclass(frozen=True, slots=True)
class PortfolioView:
    portfolio_id: UUID
    portfolio_key: str
    name: str
    kind: PortfolioKind
    base_asset_id: UUID
    status: RegistryStatus
    row_version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


@dataclass(frozen=True, slots=True)
class AssetView:
    asset_id: UUID
    asset_key: str
    symbol: str
    name: str
    asset_class: AssetClass
    precision: int
    status: RegistryStatus
    row_version: int
    created_at: datetime
    updated_at: datetime
    deactivated_at: datetime | None


@dataclass(frozen=True, slots=True)
class AssetIdentifierView:
    asset_identifier_id: UUID
    asset_id: UUID
    scheme: AssetIdentifierScheme
    value: str
    is_primary: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AccountView:
    account_id: UUID
    portfolio_id: UUID
    account_key: str
    name: str
    kind: AccountKind
    institution_name: str | None
    external_reference: str | None
    status: RegistryStatus
    row_version: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
