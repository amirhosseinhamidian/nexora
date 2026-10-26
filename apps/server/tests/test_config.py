from __future__ import annotations

import re

import pytest
from nexora.config import (
    CONFIG_SCHEMA_VERSION,
    ConfigurationError,
    DeploymentProfile,
    Locale,
    RuntimeEnvironment,
    Theme,
    load_settings,
)


def test_defaults_are_local_bilingual_and_non_secret() -> None:
    settings = load_settings({})

    assert settings.environment is RuntimeEnvironment.DEVELOPMENT
    assert settings.deployment_profile is DeploymentProfile.LOCAL_DEVELOPMENT
    assert settings.default_locale is Locale.PERSIAN
    assert settings.default_theme is Theme.SYSTEM
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert settings.debug is True
    assert settings.checksum() == "5d4f9f7b6a1b7e1d8ab7af749136afff0b9e4de419d05f34a47497e68818ea04"
    assert CONFIG_SCHEMA_VERSION == "nexora-runtime-configuration-v1"


def test_checksum_is_deterministic_and_order_independent() -> None:
    first = load_settings(
        {
            "NEXORA_DEFAULT_THEME": "dark",
            "NEXORA_DEFAULT_LOCALE": "en",
        }
    )
    second = load_settings(
        {
            "NEXORA_DEFAULT_LOCALE": "en",
            "NEXORA_DEFAULT_THEME": "dark",
        }
    )

    assert first.checksum() == second.checksum()
    assert re.fullmatch(r"[0-9a-f]{64}", first.checksum())


def test_private_production_profile_is_explicit_and_debug_is_disabled() -> None:
    settings = load_settings(
        {
            "NEXORA_ENVIRONMENT": "production",
            "NEXORA_DEPLOYMENT_PROFILE": "private_single_host",
            "NEXORA_API_HOST": "0.0.0.0",
        }
    )

    assert settings.environment is RuntimeEnvironment.PRODUCTION
    assert settings.deployment_profile is DeploymentProfile.PRIVATE_SINGLE_HOST
    assert settings.debug is False


@pytest.mark.parametrize(
    ("environ", "field"),
    [
        ({"NEXORA_ENVIRONMENT": "production"}, "private_single_host"),
        (
            {
                "NEXORA_ENVIRONMENT": "production",
                "NEXORA_DEPLOYMENT_PROFILE": "private_single_host",
                "NEXORA_LOG_LEVEL": "DEBUG",
            },
            "DEBUG",
        ),
        ({"NEXORA_API_HOST": "0.0.0.0"}, "127.0.0.1"),
        ({"NEXORA_DEPLOYMENT_PROFILE": "public_internet"}, "deployment_profile"),
        ({"NEXORA_API_PORT": "80"}, "api_port"),
        ({"NEXORA_API_PORT": "not-a-port"}, "api_port"),
    ],
)
def test_unsafe_or_invalid_configuration_fails_closed(environ: dict[str, str], field: str) -> None:
    with pytest.raises(ConfigurationError, match=field):
        load_settings(environ)


def test_unknown_prefixed_variable_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="NEXORA_DATABASE_URL"):
        load_settings({"NEXORA_DATABASE_URL": "postgresql://must-not-be-accepted-yet"})


def test_known_infrastructure_variables_do_not_enter_runtime_settings() -> None:
    settings = load_settings(
        {
            "NEXORA_DEV_DB_PASSWORD_FILE": "/private/dev-password",
            "NEXORA_MIGRATION_DATABASE_DSN_FILE": "/private/migration-dsn",
            "NEXORA_LOG_FILE": "/private/nexora.jsonl",
        }
    )

    assert settings == load_settings({})


def test_infrastructure_variable_typo_is_still_rejected() -> None:
    with pytest.raises(ConfigurationError, match="NEXORA_MIGRATION_DATABASE_DSN_FIL"):
        load_settings({"NEXORA_MIGRATION_DATABASE_DSN_FIL": "/private/migration-dsn"})


def test_blank_value_is_rejected_without_echoing_it() -> None:
    with pytest.raises(ConfigurationError, match="NEXORA_LOG_LEVEL"):
        load_settings({"NEXORA_LOG_LEVEL": "   "})


def test_unrelated_environment_variables_are_ignored() -> None:
    settings = load_settings({"PATH": "/not/used", "LANG": "fa_IR.UTF-8"})
    assert settings == load_settings({})
