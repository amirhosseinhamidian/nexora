from __future__ import annotations

import os
from pathlib import Path

import pytest
from nexora.adapters.postgresql import (
    DATABASE_DSN_FILE_ENV,
    DatabaseConfigurationError,
    load_database_settings,
)

TEST_DSN = "postgresql+psycopg://nexora_test:test_password@127.0.0.1:5432/nexora_test"


def _dsn_file(tmp_path: Path, content: str = TEST_DSN, mode: int = 0o600) -> Path:
    path = tmp_path / "database.dsn"
    path.write_text(f"{content}\n", encoding="utf-8")
    path.chmod(mode)
    return path


def test_database_settings_are_loaded_from_a_private_absolute_file(tmp_path: Path) -> None:
    path = _dsn_file(tmp_path)
    settings = load_database_settings({DATABASE_DSN_FILE_ENV: str(path)})

    assert settings.dsn.get_secret_value() == TEST_DSN
    assert "test_password" not in settings.safe_target
    assert "***" in settings.safe_target
    assert settings.dsn_file == path


def test_production_requires_exact_read_only_owner_mode(tmp_path: Path) -> None:
    path = _dsn_file(tmp_path, mode=0o400)
    settings = load_database_settings(
        {
            DATABASE_DSN_FILE_ENV: str(path),
            "NEXORA_ENVIRONMENT": "production",
        }
    )
    assert settings.dsn_file == path


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604])
def test_database_dsn_file_rejects_group_or_other_access(tmp_path: Path, mode: int) -> None:
    path = _dsn_file(tmp_path, mode=mode)
    with pytest.raises(DatabaseConfigurationError, match="group or others"):
        load_database_settings({DATABASE_DSN_FILE_ENV: str(path)})


def test_production_rejects_writable_owner_mode(tmp_path: Path) -> None:
    path = _dsn_file(tmp_path, mode=0o600)
    with pytest.raises(DatabaseConfigurationError, match="0400"):
        load_database_settings(
            {
                DATABASE_DSN_FILE_ENV: str(path),
                "NEXORA_ENVIRONMENT": "production",
            }
        )


def test_database_dsn_file_must_be_absolute() -> None:
    with pytest.raises(DatabaseConfigurationError, match="absolute"):
        load_database_settings({DATABASE_DSN_FILE_ENV: "database.dsn"})


def test_database_dsn_file_rejects_symbolic_links(tmp_path: Path) -> None:
    target = _dsn_file(tmp_path)
    link = tmp_path / "database-link.dsn"
    link.symlink_to(target)
    with pytest.raises(DatabaseConfigurationError, match="symbolic link"):
        load_database_settings({DATABASE_DSN_FILE_ENV: str(link)})


@pytest.mark.parametrize(
    "dsn",
    [
        "sqlite:///nexora.db",
        "postgresql://nexora:test@localhost/nexora",
        "postgresql+psycopg://localhost/nexora",
        "not-a-dsn",
    ],
)
def test_database_dsn_rejects_wrong_or_incomplete_targets(tmp_path: Path, dsn: str) -> None:
    path = _dsn_file(tmp_path, content=dsn)
    with pytest.raises(DatabaseConfigurationError):
        load_database_settings({DATABASE_DSN_FILE_ENV: str(path)})


def test_errors_never_echo_database_credentials(tmp_path: Path) -> None:
    secret = "do-not-echo-this-password"
    path = _dsn_file(tmp_path, content=f"postgresql+wrong://owner:{secret}@localhost/nexora")
    with pytest.raises(DatabaseConfigurationError) as raised:
        load_database_settings({DATABASE_DSN_FILE_ENV: str(path)})
    assert secret not in str(raised.value)


def test_database_dsn_file_rejects_multiple_lines(tmp_path: Path) -> None:
    path = _dsn_file(tmp_path, content=f"{TEST_DSN}\n{TEST_DSN}")
    with pytest.raises(DatabaseConfigurationError, match="exactly one"):
        load_database_settings({DATABASE_DSN_FILE_ENV: str(path)})


def test_database_settings_require_the_operator_file_variable() -> None:
    with pytest.raises(DatabaseConfigurationError, match=DATABASE_DSN_FILE_ENV):
        load_database_settings({})


def test_database_settings_reject_an_unknown_runtime_environment(tmp_path: Path) -> None:
    path = _dsn_file(tmp_path)
    with pytest.raises(DatabaseConfigurationError, match="environment"):
        load_database_settings(
            {
                DATABASE_DSN_FILE_ENV: str(path),
                "NEXORA_ENVIRONMENT": "staging",
            }
        )


def test_secret_is_not_exposed_by_settings_repr(tmp_path: Path) -> None:
    path = _dsn_file(tmp_path)
    settings = load_database_settings({DATABASE_DSN_FILE_ENV: str(path)})
    assert "test_password" not in repr(settings)


def test_test_file_mode_is_not_changed_by_loading(tmp_path: Path) -> None:
    path = _dsn_file(tmp_path, mode=0o600)
    load_database_settings({DATABASE_DSN_FILE_ENV: str(path)})
    assert os.stat(path).st_mode & 0o777 == 0o600
