from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True, slots=True)
class OverloadDecision:
    allowed: bool
    retry_after_seconds: int | None = None


class InteractiveRequestGate:
    """Process-local token bucket for the bounded single-host Web/API runtime."""

    def __init__(
        self,
        *,
        sustained_per_second: float = 10.0,
        burst: int = 25,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if sustained_per_second <= 0 or burst < 1:
            raise ValueError("interactive request budget must be positive")
        self._rate = sustained_per_second
        self._capacity = float(burst)
        self._tokens = float(burst)
        self._clock = clock
        self._observed_at = clock()
        self._lock = Lock()

    def acquire(self) -> OverloadDecision:
        with self._lock:
            now = self._clock()
            elapsed = max(0.0, now - self._observed_at)
            self._observed_at = now
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            if self._tokens + 1e-9 >= 1.0:
                self._tokens = max(0.0, self._tokens - 1.0)
                return OverloadDecision(allowed=True)
            retry_after = max(1, math.ceil((1.0 - self._tokens) / self._rate))
            return OverloadDecision(allowed=False, retry_after_seconds=retry_after)
