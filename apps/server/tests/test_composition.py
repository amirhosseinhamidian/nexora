from pathlib import Path

from nexora.adapters.trd_bot import TRD_BOT_MODE_ENV, TrdBotIntegrationMode
from nexora.composition import SERVICE_NAME, compose_application, compose_private_application
from nexora.config import CONFIG_SCHEMA_VERSION, load_settings


def test_composition_is_explicit_and_deterministic() -> None:
    settings = load_settings({})
    first = compose_application(settings)
    second = compose_application(settings)

    assert first is not second
    assert first.settings is settings
    assert first.identity == second.identity
    assert first.identity.service == SERVICE_NAME
    assert first.identity.configuration_schema == CONFIG_SCHEMA_VERSION
    assert first.identity.configuration_checksum == settings.checksum()
    assert first.observability is not second.observability
    assert first.observability.metrics.snapshot()["schema_version"] == "nexora-runtime-metrics-v1"


def test_default_composition_contains_no_side_effecting_runtime_adapters() -> None:
    container = compose_application(load_settings({}))
    assert container.database_engine is None
    assert container.identity_repository is None
    assert container.durable_work_repository is None
    assert container.security is None
    assert container.webauthn_verifier is None
    assert container.owner_identity_service is None
    assert container.trd_bot_client is None
    assert container.artifact_storage is None
    assert container.observability.settings.log_file is None


def _private_file(path: Path, value: str) -> str:
    path.write_text(f"{value}\n", encoding="utf-8")
    path.chmod(0o600)
    return str(path)


def test_private_composition_registers_identity_runtime_explicitly(tmp_path: Path) -> None:
    environ = {
        "NEXORA_DATABASE_DSN_FILE": _private_file(
            tmp_path / "database.dsn",
            "postgresql+psycopg://nexora:fixture@127.0.0.1:5432/nexora_test",
        ),
        "NEXORA_CANONICAL_ORIGIN_FILE": _private_file(tmp_path / "origin", "http://127.0.0.1:8000"),
        "NEXORA_AUTH_PEPPER_FILE": _private_file(tmp_path / "pepper", "p" * 43),
        "NEXORA_TRD_BOT_BASE_URL_FILE": _private_file(tmp_path / "trd-origin", "http://127.0.0.1:8001"),
        "NEXORA_TRD_BOT_TOKEN_FILE": _private_file(tmp_path / "trd-token", "t" * 43),
        "NEXORA_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
    }
    container = compose_private_application(environ=environ)
    try:
        assert container.database_engine is not None
        assert container.identity_repository is not None
        assert container.durable_work_repository is not None
        assert container.security is not None
        assert container.security.rp_id == "127.0.0.1"
        assert container.webauthn_verifier is not None
        assert container.owner_identity_service is not None
        assert container.trd_bot_client is not None
        assert container.artifact_storage is not None
    finally:
        if container.trd_bot_client is not None:
            container.trd_bot_client.close()
        assert container.database_engine is not None
        container.database_engine.dispose()


def test_private_composition_disables_incompatible_provider_without_credentials(tmp_path: Path) -> None:
    environ = {
        "NEXORA_DATABASE_DSN_FILE": _private_file(
            tmp_path / "database.dsn",
            "postgresql+psycopg://nexora:fixture@127.0.0.1:5432/nexora_test",
        ),
        "NEXORA_CANONICAL_ORIGIN_FILE": _private_file(tmp_path / "origin", "http://127.0.0.1:8000"),
        "NEXORA_AUTH_PEPPER_FILE": _private_file(tmp_path / "pepper", "p" * 43),
        "NEXORA_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
        TRD_BOT_MODE_ENV: "disabled_incompatible_provider",
    }
    container = compose_private_application(environ=environ)
    try:
        assert container.trd_bot_client is None
        assert container.trd_bot_integration_mode is TrdBotIntegrationMode.DISABLED_INCOMPATIBLE_PROVIDER
    finally:
        assert container.database_engine is not None
        container.database_engine.dispose()
