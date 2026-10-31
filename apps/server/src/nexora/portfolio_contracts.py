from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nexora.portfolio_registry import (
    AccountKind,
    AssetClass,
    AssetIdentifierScheme,
    PortfolioKind,
    RegistryStatus,
)


class RegistryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class CreateAssetRequest(RegistryModel):
    asset_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
    symbol: str = Field(min_length=1, max_length=24, pattern=r"^[A-Z0-9][A-Z0-9._-]{0,23}$")
    name: str = Field(min_length=1, max_length=120)
    asset_class: AssetClass
    precision: int = Field(ge=0, le=30)


class AssetResponse(RegistryModel):
    schema_version: Literal["nexora-asset-registry-v1"] = "nexora-asset-registry-v1"
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


class AssetListResponse(RegistryModel):
    schema_version: Literal["nexora-asset-registry-list-v1"] = "nexora-asset-registry-list-v1"
    items: list[AssetResponse]


class CreateAssetIdentifierRequest(RegistryModel):
    scheme: AssetIdentifierScheme
    value: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
    is_primary: bool = False


class AssetIdentifierResponse(RegistryModel):
    schema_version: Literal["nexora-asset-identifier-v1"] = "nexora-asset-identifier-v1"
    asset_identifier_id: UUID
    asset_id: UUID
    scheme: AssetIdentifierScheme
    value: str
    is_primary: bool
    created_at: datetime


class CreatePortfolioRequest(RegistryModel):
    portfolio_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=120)
    kind: PortfolioKind
    base_asset_id: UUID


class PortfolioResponse(RegistryModel):
    schema_version: Literal["nexora-portfolio-registry-v1"] = "nexora-portfolio-registry-v1"
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


class PortfolioListResponse(RegistryModel):
    schema_version: Literal["nexora-portfolio-registry-list-v1"] = "nexora-portfolio-registry-list-v1"
    items: list[PortfolioResponse]


class CreateAccountRequest(RegistryModel):
    portfolio_id: UUID
    account_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=120)
    kind: AccountKind
    institution_name: str | None = Field(default=None, min_length=1, max_length=120)
    external_reference: str | None = Field(default=None, min_length=1, max_length=160)


class AccountResponse(RegistryModel):
    schema_version: Literal["nexora-account-registry-v1"] = "nexora-account-registry-v1"
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


class AccountListResponse(RegistryModel):
    schema_version: Literal["nexora-account-registry-list-v1"] = "nexora-account-registry-list-v1"
    items: list[AccountResponse]


class LifecycleRequest(RegistryModel):
    expected_row_version: int = Field(ge=1)
