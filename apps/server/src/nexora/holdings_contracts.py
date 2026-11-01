from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from nexora.holdings_projection import BasisStatus, CostBasisMethod


class HoldingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RebuildHoldingsRequest(HoldingsModel):
    cost_basis_method: CostBasisMethod


class ProjectionCheckpointResponse(HoldingsModel):
    schema_version: Literal["nexora-holdings-projection-v1"] = "nexora-holdings-projection-v1"
    holdings_rebuild_id: UUID
    portfolio_id: UUID
    cost_basis_method: CostBasisMethod
    projection_version: str
    journal_sha256: str
    journal_transaction_count: int
    last_transaction_id: UUID | None
    rebuilt_at: datetime


class HoldingResponse(HoldingsModel):
    schema_version: Literal["nexora-holding-v1"] = "nexora-holding-v1"
    account_id: UUID
    asset_id: UUID
    quantity: str
    cost_basis_asset_id: UUID | None
    total_cost_basis: str | None
    average_unit_cost: str | None
    basis_status: BasisStatus


class LotResponse(HoldingsModel):
    schema_version: Literal["nexora-cost-basis-lot-v1"] = "nexora-cost-basis-lot-v1"
    lot_key: str
    source_lot_key: str | None
    account_id: UUID
    asset_id: UUID
    acquisition_transaction_id: UUID
    acquisition_leg_id: UUID
    acquired_at: datetime
    original_quantity: str
    remaining_quantity: str
    cost_basis_asset_id: UUID | None
    original_cost_basis: str | None
    remaining_cost_basis: str | None
    basis_status: BasisStatus


class LotConsumptionResponse(HoldingsModel):
    schema_version: Literal["nexora-lot-consumption-v1"] = "nexora-lot-consumption-v1"
    consumption_key: str
    disposal_transaction_id: UUID
    disposal_leg_id: UUID
    lot_key: str
    quantity: str
    cost_basis_asset_id: UUID | None
    allocated_cost_basis: str | None
    basis_status: BasisStatus
    sequence: int


class HoldingsProjectionResponse(HoldingsModel):
    schema_version: Literal["nexora-holdings-projection-response-v1"] = "nexora-holdings-projection-response-v1"
    checkpoint: ProjectionCheckpointResponse
    holdings: list[HoldingResponse]
    lots: list[LotResponse]
    consumptions: list[LotConsumptionResponse]


class HoldingListResponse(HoldingsModel):
    schema_version: Literal["nexora-holding-list-v1"] = "nexora-holding-list-v1"
    checkpoint: ProjectionCheckpointResponse
    items: list[HoldingResponse]


class LotListResponse(HoldingsModel):
    schema_version: Literal["nexora-cost-basis-lot-list-v1"] = "nexora-cost-basis-lot-list-v1"
    checkpoint: ProjectionCheckpointResponse
    items: list[LotResponse]
