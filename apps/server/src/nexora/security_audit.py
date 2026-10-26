from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Final

AUDIT_METADATA_MAX_BYTES: Final = 4096
_SENSITIVE_KEY_PARTS: Final = (
    "authorization",
    "cookie",
    "credential_id",
    "credential_public_key",
    "csrf",
    "password",
    "private_key",
    "recovery_code",
    "secret",
    "session_token",
    "token",
)


class SecurityAuditMetadataError(ValueError):
    pass


def sanitize_audit_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    """Reject secret-bearing or unbounded audit metadata before immutable persistence."""

    sanitized: dict[str, object] = {}
    for key, value in metadata.items():
        normalized = key.lower().replace("-", "_")
        if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
            raise SecurityAuditMetadataError(f"secret-bearing audit metadata key is forbidden: {key}")
        if not isinstance(value, (str, bool, int, float)) and value is not None:
            raise SecurityAuditMetadataError(f"audit metadata value must be scalar: {key}")
        sanitized[key] = value
    encoded = json.dumps(sanitized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > AUDIT_METADATA_MAX_BYTES:
        raise SecurityAuditMetadataError("audit metadata exceeds the size limit")
    return sanitized
