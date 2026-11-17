from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from nexora.adapters.postgresql.watchlists import (
    WatchlistCreate,
    WatchlistItemWrite,
    WatchlistPreferencesWrite,
    WatchlistRepository,
    WatchlistRepositoryConflict,
    WatchlistRepositoryNotFound,
    WatchlistView,
)

WATCHLIST_SCHEMA_VERSION: Final = "nexora-watchlists-v1"


class WatchlistError(RuntimeError):
    pass


class WatchlistNotFound(WatchlistError):
    pass


class WatchlistConflict(WatchlistError):
    pass


class WatchlistItemKind(StrEnum):
    ASSET = "asset"
    MARKET = "market"
    STRATEGY = "strategy"
    CANDIDATE_SOURCE = "candidate_source"


class PresentationOrder(StrEnum):
    NEWEST_FIRST = "newest_first"
    OLDEST_FIRST = "oldest_first"
    SEVERITY_DESC = "severity_desc"


class MinimumSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class WatchlistModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _trimmed(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("value must not be blank")
    return trimmed


class CreateWatchlistRequest(WatchlistModel):
    name: str = Field(min_length=1, max_length=120)

    _name_trimmed = field_validator("name")(_trimmed)


class CreateWatchlistItemRequest(WatchlistModel):
    item_kind: WatchlistItemKind
    reference: str = Field(min_length=1, max_length=160)
    label: str | None = Field(default=None, min_length=1, max_length=120)
    expected_version: int = Field(ge=0)

    _reference_trimmed = field_validator("reference")(_trimmed)
    _label_trimmed = field_validator("label")(lambda value: None if value is None else _trimmed(value))


class UpdateMonitoringPreferencesRequest(WatchlistModel):
    presentation_order: PresentationOrder
    minimum_severity: MinimumSeverity
    include_resolved: bool
    expected_version: int = Field(ge=0)


class WatchlistItemResponse(WatchlistModel):
    watchlist_item_id: UUID
    item_kind: WatchlistItemKind
    reference: str
    label: str | None
    created_at: datetime


class MonitoringPreferencesResponse(WatchlistModel):
    presentation_order: PresentationOrder
    minimum_severity: MinimumSeverity
    include_resolved: bool
    updated_at: datetime
    notification_delivery_enabled: Literal[False] = False
    provider_subscription_management_enabled: Literal[False] = False


class WatchlistResponse(WatchlistModel):
    watchlist_id: UUID
    name: str
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    preferences: MonitoringPreferencesResponse
    items: tuple[WatchlistItemResponse, ...]
    creates_trade_instruction: Literal[False] = False


class WatchlistListResponse(WatchlistModel):
    schema_version: Literal["nexora-watchlists-v1"] = WATCHLIST_SCHEMA_VERSION
    items: tuple[WatchlistResponse, ...]


def _response(view: WatchlistView) -> WatchlistResponse:
    return WatchlistResponse(
        watchlist_id=view.watchlist_id,
        name=view.name,
        row_version=view.row_version,
        created_at=view.created_at,
        updated_at=view.updated_at,
        preferences=MonitoringPreferencesResponse(
            presentation_order=PresentationOrder(view.preferences.presentation_order),
            minimum_severity=MinimumSeverity(view.preferences.minimum_severity),
            include_resolved=view.preferences.include_resolved,
            updated_at=view.preferences.updated_at,
        ),
        items=tuple(
            WatchlistItemResponse(
                watchlist_item_id=item.watchlist_item_id,
                item_kind=WatchlistItemKind(item.item_kind),
                reference=item.reference,
                label=item.label,
                created_at=item.created_at,
            )
            for item in view.items
        ),
    )


class WatchlistService:
    def __init__(self, repository: WatchlistRepository) -> None:
        self._repository = repository

    def list(self, owner_id: UUID, *, limit: int) -> WatchlistListResponse:
        return WatchlistListResponse(
            items=tuple(_response(item) for item in self._repository.list(owner_id, limit=limit))
        )

    def create(
        self,
        owner_id: UUID,
        request: CreateWatchlistRequest,
        *,
        idempotency_key: str,
    ) -> WatchlistResponse:
        try:
            view, _ = self._repository.create(
                owner_id,
                WatchlistCreate(name=request.name, idempotency_key=idempotency_key),
            )
        except WatchlistRepositoryNotFound as error:
            raise WatchlistNotFound(str(error)) from error
        except WatchlistRepositoryConflict as error:
            raise WatchlistConflict(str(error)) from error
        return _response(view)

    def add_item(
        self,
        owner_id: UUID,
        watchlist_id: UUID,
        request: CreateWatchlistItemRequest,
        *,
        idempotency_key: str,
    ) -> WatchlistResponse:
        try:
            view, _ = self._repository.add_item(
                owner_id,
                watchlist_id,
                WatchlistItemWrite(
                    item_kind=request.item_kind.value,
                    reference=request.reference,
                    label=request.label,
                    expected_version=request.expected_version,
                    idempotency_key=idempotency_key,
                ),
            )
        except WatchlistRepositoryNotFound as error:
            raise WatchlistNotFound(str(error)) from error
        except WatchlistRepositoryConflict as error:
            raise WatchlistConflict(str(error)) from error
        return _response(view)

    def update_preferences(
        self,
        owner_id: UUID,
        watchlist_id: UUID,
        request: UpdateMonitoringPreferencesRequest,
        *,
        idempotency_key: str,
    ) -> WatchlistResponse:
        try:
            view, _ = self._repository.update_preferences(
                owner_id,
                watchlist_id,
                WatchlistPreferencesWrite(
                    presentation_order=request.presentation_order.value,
                    minimum_severity=request.minimum_severity.value,
                    include_resolved=request.include_resolved,
                    expected_version=request.expected_version,
                    idempotency_key=idempotency_key,
                ),
            )
        except WatchlistRepositoryNotFound as error:
            raise WatchlistNotFound(str(error)) from error
        except WatchlistRepositoryConflict as error:
            raise WatchlistConflict(str(error)) from error
        return _response(view)
