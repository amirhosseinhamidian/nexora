from nexora.overload import InteractiveRequestGate


def test_production_api_returns_versioned_429_with_retry_after() -> None:
    from fastapi.testclient import TestClient
    from nexora.api import create_app
    from nexora.config import DeploymentProfile, RuntimeEnvironment, RuntimeSettings

    app = create_app(
        RuntimeSettings(
            environment=RuntimeEnvironment.PRODUCTION,
            deployment_profile=DeploymentProfile.PRIVATE_SINGLE_HOST,
            api_host="0.0.0.0",
        )
    )
    app.state.interactive_request_gate = InteractiveRequestGate(
        sustained_per_second=10,
        burst=1,
        clock=lambda: 100.0,
    )
    with TestClient(app) as client:
        client.get("/v1/session")
        response = client.get("/v1/session")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "1"
    assert response.json()["error"]["code"] == "INTERACTIVE_RATE_LIMITED"


def test_interactive_gate_allows_the_declared_burst_then_returns_retry_after() -> None:
    observed = [100.0]
    gate = InteractiveRequestGate(sustained_per_second=10, burst=25, clock=lambda: observed[0])

    assert all(gate.acquire().allowed for _ in range(25))
    denied = gate.acquire()

    assert denied.allowed is False
    assert denied.retry_after_seconds == 1


def test_interactive_gate_replenishes_without_exceeding_the_burst() -> None:
    observed = [100.0]
    gate = InteractiveRequestGate(sustained_per_second=10, burst=2, clock=lambda: observed[0])
    assert gate.acquire().allowed is True
    assert gate.acquire().allowed is True
    assert gate.acquire().allowed is False

    observed[0] += 0.1
    assert gate.acquire().allowed is True
    assert gate.acquire().allowed is False
