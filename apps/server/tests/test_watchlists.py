from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import Mock
from uuid import UUID

import pytest
from nexora.adapters.postgresql.watchlists import (
    WatchlistPreferencesView,
    WatchlistRepository,
    WatchlistRepositoryConflict,
    WatchlistView,
)
from nexora.watchlists import (
    CreateWatchlistItemRequest,
    CreateWatchlistRequest,
    MinimumSeverity,
    PresentationOrder,
    UpdateMonitoringPreferencesRequest,
    WatchlistConflict,
    WatchlistService,
)
from pydantic import ValidationError


def _view() -> WatchlistView:
    now = datetime.now(UTC)
    return WatchlistView(
        watchlist_id=UUID("d4d13930-24e5-44a2-93ef-16a603074c13"),
        name="Decision candidates",
        row_version=0,
        created_at=now,
        updated_at=now,
        preferences=WatchlistPreferencesView(
            presentation_order="newest_first",
            minimum_severity="info",
            include_resolved=False,
            updated_at=now,
        ),
        items=(),
    )


def test_watchlist_requests_trim_values_and_reject_unbounded_inputs() -> None:
    request = CreateWatchlistRequest.model_validate({"name": "  Decision candidates  "})
    assert request.name == "Decision candidates"
    item = CreateWatchlistItemRequest.model_validate(
        {
            "item_kind": "candidate_source",
            "reference": "  momentum-v3 ",
            "label": " Momentum ",
            "expected_version": 0,
        }
    )
    assert item.reference == "momentum-v3"
    assert item.label == "Momentum"
    with pytest.raises(ValidationError, match="Input should be"):
        CreateWatchlistItemRequest.model_validate(
            {
                "item_kind": "exchange_subscription",
                "reference": "provider-feed",
                "expected_version": 0,
            }
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        UpdateMonitoringPreferencesRequest.model_validate(
            {
                "presentation_order": "newest_first",
                "minimum_severity": "info",
                "include_resolved": False,
                "expected_version": 0,
                "submit_order": True,
            }
        )


def test_service_creates_owner_watchlist_with_non_executable_defaults() -> None:
    owner_id = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
    repository_mock = Mock(spec=WatchlistRepository)
    repository_mock.create.return_value = (_view(), False)
    service = WatchlistService(cast(WatchlistRepository, repository_mock))

    response = service.create(
        owner_id,
        CreateWatchlistRequest(name="Decision candidates"),
        idempotency_key="watchlist-unit-create-key-0001",
    )

    write = repository_mock.create.call_args.args[1]
    assert write.name == "Decision candidates"
    assert response.creates_trade_instruction is False
    assert response.preferences.notification_delivery_enabled is False
    assert response.preferences.provider_subscription_management_enabled is False


def test_service_maps_optimistic_conflict_without_widening_capability() -> None:
    owner_id = UUID("113f777b-f75b-46e5-91da-91d9601c03ea")
    repository_mock = Mock(spec=WatchlistRepository)
    repository_mock.update_preferences.side_effect = WatchlistRepositoryConflict("watchlist version changed")
    service = WatchlistService(cast(WatchlistRepository, repository_mock))
    request = UpdateMonitoringPreferencesRequest(
        presentation_order=PresentationOrder.SEVERITY_DESC,
        minimum_severity=MinimumSeverity.WARNING,
        include_resolved=True,
        expected_version=1,
    )

    with pytest.raises(WatchlistConflict, match="version changed"):
        service.update_preferences(
            owner_id,
            _view().watchlist_id,
            request,
            idempotency_key="watchlist-unit-preferences-key-0001",
        )
