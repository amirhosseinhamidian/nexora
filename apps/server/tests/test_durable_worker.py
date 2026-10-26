from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from nexora.adapters.postgresql.durable import JobClaim, JobCompletion
from nexora.durable_worker import DurableWorker


class FakeRepository:
    def __init__(self, claims: tuple[JobClaim, ...]) -> None:
        self.claims = claims
        self.completed: list[object] = []
        self.failed: list[tuple[object, str]] = []

    def claim_jobs(
        self,
        *,
        worker_id: str,
        job_types: tuple[str, ...],
        limit: int,
        lease_seconds: int,
    ) -> tuple[JobClaim, ...]:
        assert worker_id == "worker-1"
        assert job_types == ("sync",)
        assert limit == 10
        assert lease_seconds == 60
        return self.claims

    def complete_job(self, *, job_id: UUID, worker_id: str, completion: JobCompletion) -> None:
        assert worker_id == "worker-1"
        self.completed.append(job_id)

    def fail_job(self, *, job_id: UUID, worker_id: str, error_code: str) -> str:
        assert worker_id == "worker-1"
        self.failed.append((job_id, error_code))
        return "retry_wait"


def _claim() -> JobClaim:
    return JobClaim(
        job_id=uuid4(),
        owner_id=uuid4(),
        job_type="sync",
        payload={"cursor": "1"},
        attempt_count=1,
        max_attempts=4,
        lease_expires_at=datetime.now(UTC) + timedelta(seconds=60),
    )


def test_worker_completes_registered_job() -> None:
    claim = _claim()
    repository = FakeRepository((claim,))
    worker = DurableWorker(repository, {"sync": lambda _: JobCompletion()}, worker_id="worker-1")
    result = worker.run_once()
    assert (result.claimed, result.succeeded, result.failed) == (1, 1, 0)
    assert repository.completed == [claim.job_id]


def test_worker_converts_handler_failure_to_safe_code() -> None:
    claim = _claim()
    repository = FakeRepository((claim,))

    def fail(_: JobClaim) -> JobCompletion:
        raise TimeoutError("secret-bearing provider detail")

    worker = DurableWorker(repository, {"sync": fail}, worker_id="worker-1")
    result = worker.run_once()
    assert (result.claimed, result.succeeded, result.failed) == (1, 0, 1)
    assert repository.failed == [(claim.job_id, "HANDLER_TIMEOUT_ERROR")]


def test_worker_reports_only_bounded_cycle_metrics() -> None:
    claim = _claim()
    repository = FakeRepository((claim,))

    class Observer:
        observed: tuple[int, int, int] | None = None

        def observe_job_cycle(self, *, claimed: int, succeeded: int, failed: int) -> None:
            self.observed = (claimed, succeeded, failed)

    observer = Observer()
    worker = DurableWorker(
        repository,
        {"sync": lambda _: JobCompletion()},
        worker_id="worker-1",
        observer=observer,
    )
    worker.run_once()
    assert observer.observed == (1, 1, 0)
