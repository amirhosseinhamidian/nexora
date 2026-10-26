import pytest
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
