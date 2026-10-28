from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from pydantic import SecretStr

from nexora.adapters.trd_bot.errors import TrdBotConfigurationError

TRD_BOT_BASE_URL_FILE_ENV: Final = "NEXORA_TRD_BOT_BASE_URL_FILE"
TRD_BOT_TOKEN_FILE_ENV: Final = "NEXORA_TRD_BOT_TOKEN_FILE"
TRD_BOT_MODE_ENV: Final = "NEXORA_TRD_BOT_MODE"
RUNTIME_ENVIRONMENT_VARIABLE: Final = "NEXORA_ENVIRONMENT"
MAX_CONFIGURATION_FILE_BYTES: Final = 4096
MINIMUM_TOKEN_CHARACTERS: Final = 43


class TrdBotIntegrationMode(StrEnum):
    DISABLED_INCOMPATIBLE_PROVIDER = "disabled_incompatible_provider"
    ENABLED_COMPATIBLE_PROVIDER = "enabled_compatible_provider"


@dataclass(frozen=True, slots=True)
class TrdBotSettings:
    base_url: str
    token: SecretStr
    base_url_file: Path
    token_file: Path
    timeout_seconds: float = 10.0


def load_trd_bot_mode(environ: Mapping[str, str] | None = None) -> TrdBotIntegrationMode:
    source = os.environ if environ is None else environ
    raw = source.get(TRD_BOT_MODE_ENV, TrdBotIntegrationMode.ENABLED_COMPATIBLE_PROVIDER.value)
    try:
        return TrdBotIntegrationMode(raw)
    except ValueError as error:
        raise TrdBotConfigurationError("TRD Bot integration mode is invalid") from error


def _validate_private_file(path: Path, *, production: bool, label: str) -> None:
    if not path.is_absolute():
        raise TrdBotConfigurationError(f"{label} file path must be absolute")
    try:
        file_status = path.lstat()
    except OSError as error:
        raise TrdBotConfigurationError(f"{label} file is unavailable") from error
    if stat.S_ISLNK(file_status.st_mode):
        raise TrdBotConfigurationError(f"{label} file cannot be a symbolic link")
    if not stat.S_ISREG(file_status.st_mode):
        raise TrdBotConfigurationError(f"{label} path must reference a regular file")
    mode = stat.S_IMODE(file_status.st_mode)
    if production and mode != 0o400:
        raise TrdBotConfigurationError(f"production {label} file mode must be 0400")
    if not production and mode & 0o077:
        raise TrdBotConfigurationError(f"{label} file cannot be accessible by group or others")
    if file_status.st_size == 0 or file_status.st_size > MAX_CONFIGURATION_FILE_BYTES:
        raise TrdBotConfigurationError(f"{label} file size is invalid")


def _read_single_line(path: Path, *, label: str) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise TrdBotConfigurationError(f"{label} file cannot be read safely") from error
    lines = content.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        raise TrdBotConfigurationError(f"{label} file must contain exactly one non-empty line")
    return lines[0].strip()


def _validate_base_url(value: str, *, production: bool) -> str:
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise TrdBotConfigurationError("TRD Bot base URL contains forbidden components")
    if not parsed.hostname or parsed.path not in {"", "/"}:
        raise TrdBotConfigurationError("TRD Bot base URL must be an origin without a path")
    if production:
        if parsed.scheme != "https":
            raise TrdBotConfigurationError("production TRD Bot base URL must use HTTPS")
    elif parsed.scheme == "http":
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise TrdBotConfigurationError("development HTTP is restricted to loopback")
    elif parsed.scheme != "https":
        raise TrdBotConfigurationError("TRD Bot base URL scheme is invalid")
    return value.rstrip("/")


def load_trd_bot_settings(environ: Mapping[str, str] | None = None) -> TrdBotSettings:
    source = os.environ if environ is None else environ
    environment = source.get(RUNTIME_ENVIRONMENT_VARIABLE, "development")
    if environment not in {"development", "test", "production"}:
        raise TrdBotConfigurationError("TRD Bot adapter environment is invalid")
    production = environment == "production"

    paths: dict[str, Path] = {}
    for variable, label in (
        (TRD_BOT_BASE_URL_FILE_ENV, "TRD Bot base URL"),
        (TRD_BOT_TOKEN_FILE_ENV, "TRD Bot token"),
    ):
        raw = source.get(variable)
        if raw is None or not raw.strip():
            raise TrdBotConfigurationError(f"{variable} is required")
        path = Path(raw)
        _validate_private_file(path, production=production, label=label)
        paths[variable] = path

    base_url_file = paths[TRD_BOT_BASE_URL_FILE_ENV]
    token_file = paths[TRD_BOT_TOKEN_FILE_ENV]
    base_url = _validate_base_url(_read_single_line(base_url_file, label="TRD Bot base URL"), production=production)
    token = _read_single_line(token_file, label="TRD Bot token")
    if len(token) < MINIMUM_TOKEN_CHARACTERS or any(character.isspace() for character in token):
        raise TrdBotConfigurationError("TRD Bot token representation is invalid")
    return TrdBotSettings(
        base_url=base_url,
        token=SecretStr(token),
        base_url_file=base_url_file,
        token_file=token_file,
    )
