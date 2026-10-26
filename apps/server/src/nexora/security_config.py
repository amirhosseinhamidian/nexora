from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from pydantic import SecretStr

CANONICAL_ORIGIN_FILE_ENV: Final = "NEXORA_CANONICAL_ORIGIN_FILE"
AUTH_PEPPER_FILE_ENV: Final = "NEXORA_AUTH_PEPPER_FILE"
RUNTIME_ENVIRONMENT_VARIABLE: Final = "NEXORA_ENVIRONMENT"
MAX_SECRET_FILE_BYTES: Final = 4096


class SecurityConfigurationError(ValueError):
    """Raised when private identity runtime configuration is unsafe."""


@dataclass(frozen=True, slots=True)
class SecuritySettings:
    canonical_origin: str
    rp_id: str
    auth_pepper: SecretStr
    canonical_origin_file: Path
    auth_pepper_file: Path


def _read_private_line(path: Path, *, label: str, production: bool) -> str:
    if not path.is_absolute():
        raise SecurityConfigurationError(f"{label} file path must be absolute")
    try:
        file_status = path.lstat()
    except OSError as error:
        raise SecurityConfigurationError(f"{label} file is unavailable") from error
    if stat.S_ISLNK(file_status.st_mode) or not stat.S_ISREG(file_status.st_mode):
        raise SecurityConfigurationError(f"{label} path must be a regular non-symbolic file")
    mode = stat.S_IMODE(file_status.st_mode)
    if (production and mode != 0o400) or (not production and mode & 0o077):
        raise SecurityConfigurationError(f"{label} file permissions are unsafe")
    if file_status.st_size == 0 or file_status.st_size > MAX_SECRET_FILE_BYTES:
        raise SecurityConfigurationError(f"{label} file size is invalid")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise SecurityConfigurationError(f"{label} file cannot be read safely") from error
    if len(lines) != 1 or not lines[0].strip():
        raise SecurityConfigurationError(f"{label} file must contain one non-empty line")
    return lines[0].strip()


def load_security_settings(environ: Mapping[str, str] | None = None) -> SecuritySettings:
    source = os.environ if environ is None else environ
    environment = source.get(RUNTIME_ENVIRONMENT_VARIABLE, "development")
    if environment not in {"development", "test", "production"}:
        raise SecurityConfigurationError("identity runtime environment is invalid")
    production = environment == "production"
    paths: dict[str, Path] = {}
    for variable in (CANONICAL_ORIGIN_FILE_ENV, AUTH_PEPPER_FILE_ENV):
        raw_path = source.get(variable)
        if raw_path is None or not raw_path.strip():
            raise SecurityConfigurationError(f"{variable} is required")
        paths[variable] = Path(raw_path)

    origin = _read_private_line(paths[CANONICAL_ORIGIN_FILE_ENV], label="canonical origin", production=production)
    parsed = urlsplit(origin)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise SecurityConfigurationError("canonical origin must be an origin without credentials or a path")
    if not parsed.hostname or (production and parsed.scheme != "https"):
        raise SecurityConfigurationError("production canonical origin must use HTTPS")
    if not production and parsed.scheme not in {"http", "https"}:
        raise SecurityConfigurationError("canonical origin scheme is invalid")
    if not production and parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SecurityConfigurationError("development HTTP origin must use loopback")

    pepper = _read_private_line(paths[AUTH_PEPPER_FILE_ENV], label="authentication pepper", production=production)
    if len(pepper) < 43 or any(character.isspace() for character in pepper):
        raise SecurityConfigurationError("authentication pepper must represent at least 256 random bits")
    return SecuritySettings(
        canonical_origin=origin.rstrip("/"),
        rp_id=parsed.hostname,
        auth_pepper=SecretStr(pepper),
        canonical_origin_file=paths[CANONICAL_ORIGIN_FILE_ENV],
        auth_pepper_file=paths[AUTH_PEPPER_FILE_ENV],
    )
