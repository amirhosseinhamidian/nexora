from nexora.composition import SERVICE_NAME, compose_application
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


def test_composition_contains_no_deferred_runtime_adapters() -> None:
    container = compose_application(load_settings({}))
    assert set(container.__dataclass_fields__) == {"settings", "identity"}
