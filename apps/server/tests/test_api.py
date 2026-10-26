import pytest
from httpx import ASGITransport, AsyncClient
from nexora.api import create_app
from nexora.composition import ApplicationContainer
from nexora.config import load_settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_liveness_is_minimal_and_versioned() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "service": "nexora-api",
        "status": "ok",
        "version": "0.1.0",
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    assert "unsafe-inline" not in response.headers["content-security-policy"]


@pytest.mark.anyio
async def test_interactive_documentation_is_not_exposed_by_bootstrap() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/redoc")).status_code == 404


def test_app_uses_an_explicit_immutable_composition_container() -> None:
    settings = load_settings({"NEXORA_DEFAULT_LOCALE": "en"})
    application = create_app(settings)

    assert isinstance(application.state.container, ApplicationContainer)
    assert application.state.container.settings is settings
    assert application.state.container.identity.configuration_checksum == settings.checksum()


@pytest.mark.anyio
async def test_readiness_fails_closed_without_private_runtime() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_configured"}
