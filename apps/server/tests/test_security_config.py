from __future__ import annotations

from pathlib import Path

import pytest
from nexora.security_config import SecurityConfigurationError, load_security_settings


def _private_file(path: Path, value: str, mode: int = 0o600) -> Path:
    path.write_text(f"{value}\n", encoding="utf-8")
    path.chmod(mode)
    return path


def test_development_security_configuration_is_file_only(tmp_path: Path) -> None:
    origin = _private_file(tmp_path / "origin", "http://127.0.0.1:8000")
    pepper = _private_file(tmp_path / "pepper", "p" * 43)
    settings = load_security_settings(
        {
            "NEXORA_CANONICAL_ORIGIN_FILE": str(origin),
            "NEXORA_AUTH_PEPPER_FILE": str(pepper),
        }
    )
    assert settings.canonical_origin == "http://127.0.0.1:8000"
    assert settings.rp_id == "127.0.0.1"
    assert "p" * 43 not in repr(settings)


def test_production_requires_https_and_mode_0400(tmp_path: Path) -> None:
    origin = _private_file(tmp_path / "origin", "https://nexora.private", 0o400)
    pepper = _private_file(tmp_path / "pepper", "p" * 43, 0o400)
    settings = load_security_settings(
        {
            "NEXORA_ENVIRONMENT": "production",
            "NEXORA_CANONICAL_ORIGIN_FILE": str(origin),
            "NEXORA_AUTH_PEPPER_FILE": str(pepper),
        }
    )
    assert settings.rp_id == "nexora.private"

    pepper.chmod(0o600)
    with pytest.raises(SecurityConfigurationError, match="permissions"):
        load_security_settings(
            {
                "NEXORA_ENVIRONMENT": "production",
                "NEXORA_CANONICAL_ORIGIN_FILE": str(origin),
                "NEXORA_AUTH_PEPPER_FILE": str(pepper),
            }
        )


def test_missing_or_public_http_configuration_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SecurityConfigurationError, match="NEXORA_CANONICAL_ORIGIN_FILE"):
        load_security_settings({})
    origin = _private_file(tmp_path / "origin", "http://example.com")
    pepper = _private_file(tmp_path / "pepper", "p" * 43)
    with pytest.raises(SecurityConfigurationError, match="loopback"):
        load_security_settings(
            {
                "NEXORA_CANONICAL_ORIGIN_FILE": str(origin),
                "NEXORA_AUTH_PEPPER_FILE": str(pepper),
            }
        )
