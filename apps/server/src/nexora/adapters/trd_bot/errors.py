from __future__ import annotations


class TrdBotAdapterError(RuntimeError):
    """Base exception for the versioned TRD Bot boundary."""


class TrdBotConfigurationError(TrdBotAdapterError):
    """Raised when operator-owned adapter configuration is unsafe."""


class CapabilityNegotiationRequired(TrdBotAdapterError):
    """Raised when an operation is attempted before capability negotiation."""


class IncompatibleProviderError(TrdBotAdapterError):
    """Raised when the provider release or capabilities cannot satisfy v1."""


class TrdBotSchemaError(TrdBotAdapterError):
    """Raised when a response does not match the frozen schema."""


class TrdBotResponseError(TrdBotAdapterError):
    def __init__(self, status_code: int, code: str, *, retryable: bool) -> None:
        super().__init__(f"TRD Bot request failed: status={status_code}, code={code}, retryable={retryable}")
        self.status_code = status_code
        self.code = code
        self.retryable = retryable


class CursorExpiredError(TrdBotResponseError):
    """Signals that a full snapshot resync is required."""
