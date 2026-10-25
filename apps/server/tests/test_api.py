import pytest
from httpx import ASGITransport, AsyncClient
from nexora.api import create_app


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


@pytest.mark.anyio
async def test_interactive_documentation_is_not_exposed_by_bootstrap() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/redoc")).status_code == 404
