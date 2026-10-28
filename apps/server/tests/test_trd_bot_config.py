from __future__ import annotations

from pathlib import Path

import pytest
from nexora.adapters.trd_bot import (
    TRD_BOT_BASE_URL_FILE_ENV,
    TRD_BOT_MODE_ENV,
    TRD_BOT_TOKEN_FILE_ENV,
    TrdBotConfigurationError,
    TrdBotIntegrationMode,
    load_trd_bot_mode,
    load_trd_bot_settings,
)

TOKEN = "a" * 43


def _file(tmp_path: Path, name: str, value: str, *, mode: int = 0o600) -> Path:
    path = tmp_path / name
    path.write_text(f"{value}\n", encoding="utf-8")
    path.chmod(mode)
    return path


def _environment(tmp_path: Path, *, base_url: str = "http://127.0.0.1:8080") -> dict[str, str]:
    return {
        TRD_BOT_BASE_URL_FILE_ENV: str(_file(tmp_path, "trd-bot.url", base_url)),
        TRD_BOT_TOKEN_FILE_ENV: str(_file(tmp_path, "trd-bot.token", TOKEN)),
        "NEXORA_ENVIRONMENT": "test",
    }


def test_settings_load_from_private_files_without_exposing_token(tmp_path: Path) -> None:
    settings = load_trd_bot_settings(_environment(tmp_path))

    assert settings.base_url == "http://127.0.0.1:8080"
    assert settings.token.get_secret_value() == TOKEN
    assert TOKEN not in repr(settings)


def test_incompatible_provider_mode_is_explicit_and_fail_closed() -> None:
    assert load_trd_bot_mode({TRD_BOT_MODE_ENV: "disabled_incompatible_provider"}) is (
        TrdBotIntegrationMode.DISABLED_INCOMPATIBLE_PROVIDER
    )


def test_unknown_integration_mode_is_rejected() -> None:
    with pytest.raises(TrdBotConfigurationError, match="mode"):
        load_trd_bot_mode({TRD_BOT_MODE_ENV: "legacy_read_only"})


def test_production_requires_https_and_read_only_files(tmp_path: Path) -> None:
    base_url = _file(tmp_path, "trd-bot.url", "https://trd-bot.private", mode=0o400)
    token = _file(tmp_path, "trd-bot.token", TOKEN, mode=0o400)

    settings = load_trd_bot_settings(
        {
            TRD_BOT_BASE_URL_FILE_ENV: str(base_url),
            TRD_BOT_TOKEN_FILE_ENV: str(token),
            "NEXORA_ENVIRONMENT": "production",
        }
    )

    assert settings.base_url == "https://trd-bot.private"


@pytest.mark.parametrize(
    "base_url",
    [
        "http://trd-bot.private",
        "ftp://127.0.0.1",
        "https://user:password@trd-bot.private",
        "https://trd-bot.private/api",
        "https://trd-bot.private?token=forbidden",
    ],
)
def test_unsafe_base_urls_are_rejected(tmp_path: Path, base_url: str) -> None:
    with pytest.raises(TrdBotConfigurationError):
        load_trd_bot_settings(_environment(tmp_path, base_url=base_url))


def test_development_plain_http_is_loopback_only(tmp_path: Path) -> None:
    with pytest.raises(TrdBotConfigurationError, match="loopback"):
        load_trd_bot_settings(_environment(tmp_path, base_url="http://trd-bot.private"))


def test_configuration_files_must_be_private(tmp_path: Path) -> None:
    environ = _environment(tmp_path)
    Path(environ[TRD_BOT_TOKEN_FILE_ENV]).chmod(0o644)

    with pytest.raises(TrdBotConfigurationError, match="group or others"):
        load_trd_bot_settings(environ)


def test_configuration_files_cannot_be_symbolic_links(tmp_path: Path) -> None:
    environ = _environment(tmp_path)
    target = Path(environ[TRD_BOT_TOKEN_FILE_ENV])
    link = tmp_path / "token-link"
    link.symlink_to(target)
    environ[TRD_BOT_TOKEN_FILE_ENV] = str(link)

    with pytest.raises(TrdBotConfigurationError, match="symbolic link"):
        load_trd_bot_settings(environ)


def test_short_token_is_rejected_without_echoing_it(tmp_path: Path) -> None:
    environ = _environment(tmp_path)
    secret = "too-short"
    Path(environ[TRD_BOT_TOKEN_FILE_ENV]).write_text(secret, encoding="utf-8")

    with pytest.raises(TrdBotConfigurationError) as raised:
        load_trd_bot_settings(environ)
    assert secret not in str(raised.value)
