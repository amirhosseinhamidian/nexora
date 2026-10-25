import pytest
from nexora.worker import main


def test_worker_check_does_not_claim_runtime_work(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--check"]) == 0
    assert "ready for P1-05" in capsys.readouterr().out


def test_worker_refuses_to_run_before_durable_jobs_exist() -> None:
    with pytest.raises(SystemExit, match="unavailable until NEX-P1-05"):
        main([])
