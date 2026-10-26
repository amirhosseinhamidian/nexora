from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from nexora.adapters.postgresql.durable import JobClaim, JobCompletion

JobHandler = Callable[[JobClaim], JobCompletion]


class DurableJobRepository(Protocol):
    def claim_jobs(
        self,
        *,
        worker_id: str,
        job_types: tuple[str, ...],
        limit: int,
        lease_seconds: int,
    ) -> tuple[JobClaim, ...]: ...

    def complete_job(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        completion: JobCompletion,
    ) -> None: ...

    def fail_job(self, *, job_id: UUID, worker_id: str, error_code: str) -> str: ...


def _error_code(error: Exception) -> str:
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", type(error).__name__).upper()
    return f"HANDLER_{name}"[:80]


@dataclass(frozen=True, slots=True)
class WorkerCycleResult:
    claimed: int
    succeeded: int
    failed: int


class DurableWorker:
    """Runs one bounded cycle over an explicit, dependency-injected handler allowlist."""

    def __init__(
        self,
        repository: DurableJobRepository,
        handlers: Mapping[str, JobHandler],
        *,
        worker_id: str,
        batch_size: int = 10,
        lease_seconds: int = 60,
    ) -> None:
        if not handlers:
            raise ValueError("at least one explicit job handler is required")
        if batch_size < 1 or lease_seconds < 1:
            raise ValueError("batch_size and lease_seconds must be positive")
        self._repository = repository
        self._handlers = dict(handlers)
        self._worker_id = worker_id
        self._batch_size = batch_size
        self._lease_seconds = lease_seconds

    def run_once(self) -> WorkerCycleResult:
        claims = self._repository.claim_jobs(
            worker_id=self._worker_id,
            job_types=tuple(sorted(self._handlers)),
            limit=self._batch_size,
            lease_seconds=self._lease_seconds,
        )
        succeeded = 0
        failed = 0
        for claim in claims:
            try:
                completion = self._handlers[claim.job_type](claim)
                self._repository.complete_job(
                    job_id=claim.job_id,
                    worker_id=self._worker_id,
                    completion=completion,
                )
                succeeded += 1
            except Exception as error:
                self._repository.fail_job(
                    job_id=claim.job_id,
                    worker_id=self._worker_id,
                    error_code=_error_code(error),
                )
                failed += 1
        return WorkerCycleResult(claimed=len(claims), succeeded=succeeded, failed=failed)
