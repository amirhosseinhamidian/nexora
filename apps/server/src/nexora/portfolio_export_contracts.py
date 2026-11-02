from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from nexora.portfolio_export import JsonValue, PortfolioExportFormat, PortfolioExportProfile


class PortfolioExportContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreatePortfolioExportRequest(PortfolioExportContractModel):
    profile: PortfolioExportProfile
    formats: list[PortfolioExportFormat] = Field(min_length=1, max_length=3)
    pinned: bool = False

    @field_validator("formats")
    @classmethod
    def formats_are_unique(cls, value: list[PortfolioExportFormat]) -> list[PortfolioExportFormat]:
        if len(value) != len(set(value)):
            raise ValueError("export formats must be unique")
        return value


class PortfolioExportFileResponse(PortfolioExportContractModel):
    path: str
    format: PortfolioExportFormat
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PortfolioExportManifestResponse(PortfolioExportContractModel):
    schema_version: Literal["nexora-portfolio-export-manifest-v1"]
    export_id: str = Field(pattern=r"^pex_[0-9a-f]{24}$")
    profile: PortfolioExportProfile
    delivery_format: Literal["zip_bundle"]
    content_formats: list[PortfolioExportFormat]
    generated_at: datetime
    owner_scope_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    complete: Literal[True]
    record_count: int = Field(ge=0)
    dataset_counts: dict[str, int]
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    lineage: dict[str, JsonValue]
    uncertainty: dict[str, JsonValue]
    excluded_fields: list[str]
    files: list[PortfolioExportFileResponse]
    public_download: Literal[False]


class CreatePortfolioExportResponse(PortfolioExportContractModel):
    schema_version: Literal["nexora-portfolio-export-publication-v1"] = "nexora-portfolio-export-publication-v1"
    manifest: PortfolioExportManifestResponse
    artifact_version: str
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_size_bytes: int = Field(ge=0)
    retention_class: Literal["pinned_export", "unpinned_export"]
    download_path: str


class ProjectionLineageResponse(PortfolioExportContractModel):
    source_reference_id: UUID
    source_entity_type: str
    source_entity_id: str
    source_schema_version: str
    source_version: str
    source_observed_at: datetime
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PaperShadowPortfolioResponse(PortfolioExportContractModel):
    portfolio_id: str
    mode: Literal["paper", "shadow"]
    name: str
    base_asset_symbol: str
    status: Literal["active", "closed"]
    aggregate_version: int = Field(ge=1)
    as_of: datetime
    lineage: ProjectionLineageResponse


class PaperShadowPositionResponse(PortfolioExportContractModel):
    position_id: str
    portfolio_id: str
    mode: Literal["paper", "shadow"]
    asset_symbol: str
    quantity: str
    average_entry_price: str | None
    status: Literal["open", "closed"]
    aggregate_version: int = Field(ge=1)
    as_of: datetime
    lineage: ProjectionLineageResponse


class ProjectionIssueResponse(PortfolioExportContractModel):
    code: str
    source_reference_id: UUID | None
    source_entity_id: str | None
    message: str


class PaperShadowProjectionResponse(PortfolioExportContractModel):
    projection_version: Literal["nexora-trd-bot-paper-shadow-projection-v1"]
    complete: bool
    evidence_count: int = Field(ge=0)
    portfolios: list[PaperShadowPortfolioResponse]
    positions: list[PaperShadowPositionResponse]
    issues: list[ProjectionIssueResponse]
    projection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
