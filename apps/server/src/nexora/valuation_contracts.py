from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nexora.valuation import ValuationEvidenceKind, ValuationEvidenceState, ValuationSourceKind


class ValuationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRequest(ValuationModel):
    idempotency_key: str = Field(min_length=1, max_length=160)
    source_reference: str = Field(min_length=1, max_length=160)
    source_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    valid_until: datetime


class CreatePriceObservationRequest(EvidenceRequest):
    asset_id: UUID
    quote_asset_id: UUID
    price: str = Field(pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,30})?$")
    source_kind: ValuationSourceKind


class CreateFxRateObservationRequest(EvidenceRequest):
    base_asset_id: UUID
    quote_asset_id: UUID
    rate: str = Field(pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,30})?$")
    source_kind: ValuationSourceKind


class CreateManualValuationRequest(ValuationModel):
    portfolio_id: UUID
    asset_id: UUID
    quote_asset_id: UUID
    unit_value: str = Field(pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,30})?$")
    valued_at: datetime
    valid_until: datetime
    reason: str = Field(min_length=8, max_length=500)
    source_reference: str = Field(min_length=1, max_length=160)
    source_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=1, max_length=160)


class PriceObservationResponse(ValuationModel):
    schema_version: Literal["nexora-price-observation-v1"] = "nexora-price-observation-v1"
    price_observation_id: UUID
    asset_id: UUID
    quote_asset_id: UUID
    price: str
    observed_at: datetime
    valid_until: datetime
    state: ValuationEvidenceState
    source_kind: ValuationSourceKind
    source_reference: str
    source_payload_sha256: str
    recorded_at: datetime


class PriceObservationListResponse(ValuationModel):
    schema_version: Literal["nexora-price-observation-list-v1"] = "nexora-price-observation-list-v1"
    items: list[PriceObservationResponse]


class FxRateObservationResponse(ValuationModel):
    schema_version: Literal["nexora-fx-rate-observation-v1"] = "nexora-fx-rate-observation-v1"
    fx_rate_observation_id: UUID
    base_asset_id: UUID
    quote_asset_id: UUID
    rate: str
    observed_at: datetime
    valid_until: datetime
    state: ValuationEvidenceState
    source_kind: ValuationSourceKind
    source_reference: str
    source_payload_sha256: str
    recorded_at: datetime


class FxRateObservationListResponse(ValuationModel):
    schema_version: Literal["nexora-fx-rate-observation-list-v1"] = "nexora-fx-rate-observation-list-v1"
    items: list[FxRateObservationResponse]


class ManualValuationResponse(ValuationModel):
    schema_version: Literal["nexora-manual-valuation-v1"] = "nexora-manual-valuation-v1"
    manual_valuation_id: UUID
    portfolio_id: UUID
    asset_id: UUID
    quote_asset_id: UUID
    unit_value: str
    valued_at: datetime
    valid_until: datetime
    state: ValuationEvidenceState
    reason: str
    source_reference: str
    source_payload_sha256: str
    recorded_at: datetime


class ManualValuationListResponse(ValuationModel):
    schema_version: Literal["nexora-manual-valuation-list-v1"] = "nexora-manual-valuation-list-v1"
    items: list[ManualValuationResponse]


class ValuationStatusResponse(ValuationModel):
    schema_version: Literal["nexora-valuation-status-v1"] = "nexora-valuation-status-v1"
    asset_id: UUID
    quote_asset_id: UUID
    as_of: datetime
    state: ValuationEvidenceState
    evidence_kind: ValuationEvidenceKind
    unit_value: str | None
    evidence_id: UUID | None
    evidence_at: datetime | None
    valid_until: datetime | None
    source_reference: str | None


class PortfolioValuationStatusResponse(ValuationModel):
    schema_version: Literal["nexora-portfolio-valuation-status-v1"] = "nexora-portfolio-valuation-status-v1"
    portfolio_id: UUID
    base_asset_id: UUID
    as_of: datetime
    items: list[ValuationStatusResponse]
