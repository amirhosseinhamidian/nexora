from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import SecretStr
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

DATABASE_DSN_FILE_ENV: Final = "NEXORA_MIGRATION_DATABASE_DSN_FILE"
RUNTIME_ENVIRONMENT_VARIABLE: Final = "NEXORA_ENVIRONMENT"
MAX_DSN_FILE_BYTES: Final = 4096
ALLOWED_DRIVER: Final = "postgresql+psycopg"


class DatabaseConfigurationError(ValueError):
    """Raised when the operator-supplied database configuration is unsafe."""


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    dsn: SecretStr
    safe_target: str
    dsn_file: Path
    pool_size: int = 5
    max_overflow: int = 5
    pool_timeout_seconds: int = 10


def _validate_file(path: Path, *, production: bool) -> None:
    if not path.is_absolute():
        raise DatabaseConfigurationError("database DSN file path must be absolute")
    try:
        file_status = path.lstat()
    except OSError as error:
        raise DatabaseConfigurationError("database DSN file is unavailable") from error
    if stat.S_ISLNK(file_status.st_mode):
        raise DatabaseConfigurationError("database DSN file cannot be a symbolic link")
    if not stat.S_ISREG(file_status.st_mode):
        raise DatabaseConfigurationError("database DSN path must reference a regular file")
    mode = stat.S_IMODE(file_status.st_mode)
    if production and mode != 0o400:
        raise DatabaseConfigurationError("production database DSN file mode must be 0400")
    if not production and mode & 0o077:
        raise DatabaseConfigurationError("database DSN file cannot be readable or writable by group or others")
    if file_status.st_size == 0 or file_status.st_size > MAX_DSN_FILE_BYTES:
        raise DatabaseConfigurationError("database DSN file size is invalid")


def _read_dsn(path: Path) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise DatabaseConfigurationError("database DSN file cannot be read safely") from error
    lines = content.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        raise DatabaseConfigurationError("database DSN file must contain exactly one non-empty line")
    return lines[0].strip()


def _validate_url(dsn: str) -> URL:
    try:
        url = make_url(dsn)
    except ArgumentError as error:
        raise DatabaseConfigurationError("database DSN is invalid") from error
    if url.drivername != ALLOWED_DRIVER:
        raise DatabaseConfigurationError("database DSN must use postgresql+psycopg")
    if not url.username or not url.database:
        raise DatabaseConfigurationError("database DSN requires an explicit user and database")
    return url


def load_database_settings(environ: Mapping[str, str] | None = None) -> DatabaseSettings:
    source = os.environ if environ is None else environ
    raw_path = source.get(DATABASE_DSN_FILE_ENV)
    if raw_path is None or not raw_path.strip():
        raise DatabaseConfigurationError(f"{DATABASE_DSN_FILE_ENV} is required")
    path = Path(raw_path)
    environment = source.get(RUNTIME_ENVIRONMENT_VARIABLE, "development")
    if environment not in {"development", "test", "production"}:
        raise DatabaseConfigurationError("database migration environment is invalid")
    production = environment == "production"
    _validate_file(path, production=production)
    url = _validate_url(_read_dsn(path))
    return DatabaseSettings(
        dsn=SecretStr(url.render_as_string(hide_password=False)),
        safe_target=url.render_as_string(hide_password=True),
        dsn_file=path,
    )
