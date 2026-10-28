from types import SimpleNamespace

import pytest
from nexora import worker
from nexora.adapters.trd_bot import TrdBotIntegrationMode
from nexora.config import ConfigurationError
from nexora.worker import main


def test_worker_check_does_not_claim_runtime_work(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--check"], {}) == 0
    output = capsys.readouterr().out
    assert "configuration" in output
    assert "durable-job engine ready" in output


def test_worker_refuses_to_claim_without_registered_handlers() -> None:
    with pytest.raises(SystemExit, match="no durable job handlers are registered"):
        main([], {})


def test_worker_check_fails_closed_on_unknown_configuration() -> None:
    with pytest.raises(ConfigurationError, match="NEXORA_DATABASE_URL"):
        main(["--check"], {"NEXORA_DATABASE_URL": "not-enabled"})


def test_worker_once_idles_when_incompatible_provider_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    container = SimpleNamespace(
        durable_work_repository=object(),
        trd_bot_client=None,
        trd_bot_integration_mode=TrdBotIntegrationMode.DISABLED_INCOMPATIBLE_PROVIDER,
        database_engine=None,
    )
    monkeypatch.setattr(worker, "compose_private_application", lambda *, environ: container)

    assert main(["--once"], {}) == 0
    assert "integration=disabled_incompatible_provider" in capsys.readouterr().out
