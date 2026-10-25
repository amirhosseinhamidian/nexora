"""Fail-closed client adapter for the versioned TRD Bot integration boundary."""

from nexora.adapters.trd_bot.client import API_NAMESPACE, CONTRACT_VERSION, TrdBotClient
from nexora.adapters.trd_bot.config import (
    TRD_BOT_BASE_URL_FILE_ENV,
    TRD_BOT_TOKEN_FILE_ENV,
    TrdBotSettings,
    load_trd_bot_settings,
)
from nexora.adapters.trd_bot.errors import (
    CapabilityNegotiationRequired,
    CursorExpiredError,
    IncompatibleProviderError,
    TrdBotAdapterError,
    TrdBotConfigurationError,
    TrdBotResponseError,
    TrdBotSchemaError,
)
from nexora.adapters.trd_bot.models import (
    CapabilitiesResponse,
    CommandReceipt,
    CommandType,
    DecisionReviewCommand,
    EventEnvelope,
    EventPage,
    EventType,
    ExportManifest,
    ExportRequest,
    ExportStatus,
    ResourceType,
    SnapshotPage,
    SourceReference,
)

__all__ = [
    "API_NAMESPACE",
    "CONTRACT_VERSION",
    "TRD_BOT_BASE_URL_FILE_ENV",
    "TRD_BOT_TOKEN_FILE_ENV",
    "CapabilitiesResponse",
    "CapabilityNegotiationRequired",
    "CommandReceipt",
    "CommandType",
    "CursorExpiredError",
    "DecisionReviewCommand",
    "EventEnvelope",
    "EventPage",
    "EventType",
    "ExportManifest",
    "ExportRequest",
    "ExportStatus",
    "IncompatibleProviderError",
    "ResourceType",
    "SnapshotPage",
    "SourceReference",
    "TrdBotAdapterError",
    "TrdBotClient",
    "TrdBotConfigurationError",
    "TrdBotResponseError",
    "TrdBotSchemaError",
    "TrdBotSettings",
    "load_trd_bot_settings",
]
