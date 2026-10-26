"""PostgreSQL persistence primitives without application startup side effects."""

from nexora.adapters.postgresql.base import (
    ALEMBIC_VERSION_SCHEMA,
    DATABASE_SESSION_OPTIONS,
    NAMING_CONVENTION,
    SCHEMA_NAME,
    Base,
)
from nexora.adapters.postgresql.config import (
    DATABASE_DSN_FILE_ENV,
    DatabaseConfigurationError,
    DatabaseSettings,
    load_database_settings,
)
from nexora.adapters.postgresql.durable import (
    CheckpointAdvance,
    CheckpointConflict,
    DurableWorkError,
    DurableWorkRepository,
    IdempotencyConflict,
    JobClaim,
    JobCompletion,
    LeaseLost,
    OutboxClaim,
    OutboxMessage,
    canonical_payload_sha256,
    retry_delay,
)
from nexora.adapters.postgresql.engine import create_database_engine, create_session_factory, probe_database
from nexora.adapters.postgresql.models import (
    BackgroundJob,
    ImmutableSourceEvidence,
    OutboxEvent,
    OwnerProfile,
    ProjectionCheckpoint,
    SourceReference,
)

__all__ = [
    "ALEMBIC_VERSION_SCHEMA",
    "DATABASE_DSN_FILE_ENV",
    "DATABASE_SESSION_OPTIONS",
    "NAMING_CONVENTION",
    "SCHEMA_NAME",
    "BackgroundJob",
    "Base",
    "CheckpointAdvance",
    "CheckpointConflict",
    "DatabaseConfigurationError",
    "DatabaseSettings",
    "DurableWorkError",
    "DurableWorkRepository",
    "IdempotencyConflict",
    "ImmutableSourceEvidence",
    "JobClaim",
    "JobCompletion",
    "LeaseLost",
    "OutboxClaim",
    "OutboxEvent",
    "OutboxMessage",
    "OwnerProfile",
    "ProjectionCheckpoint",
    "SourceReference",
    "canonical_payload_sha256",
    "create_database_engine",
    "create_session_factory",
    "load_database_settings",
    "probe_database",
    "retry_delay",
]
