"""Minimal, privacy-conscious execution observability."""

from __future__ import annotations

import logging
import threading
from collections import Counter, deque
from dataclasses import dataclass
from typing import Literal, Protocol

from .logging_config import log_event

Outcome = Literal["success", "failure"]


@dataclass(frozen=True)
class ExecutionObservation:
    """A privacy-safe record of one execution attempt."""

    task_id: object
    provider: str | None
    model: str | None
    duration_ms: int
    outcome: Outcome
    error_category: str | None = None


class ExecutionObserver(Protocol):
    """Callable observer for execution observations."""

    def __call__(self, observation: ExecutionObservation) -> None:
        """Record one execution observation."""


logger = logging.getLogger(__name__)


def log_observation(observation: ExecutionObservation) -> None:
    """Log an observation without prompts, outputs, keys, or raw errors."""

    log_event(
        logger,
        logging.INFO,
        "task_execution",
        task_id=observation.task_id,
        provider=observation.provider,
        model=observation.model,
        duration_ms=observation.duration_ms,
        outcome=observation.outcome,
        error_category=observation.error_category,
    )


class ExecutionMetrics:
    """A bounded, in-memory collector for execution observations."""

    def __init__(
        self,
        max_observations: int = 100,
        *,
        maxlen: int | None = None,
        capacity: int | None = None,
        max_size: int | None = None,
        max_recent: int | None = None,
        max_history: int | None = None,
        limit: int | None = None,
    ) -> None:
        for candidate in (maxlen, capacity, max_size, max_recent, max_history, limit):
            if candidate is not None:
                max_observations = candidate

        if not isinstance(max_observations, int) or max_observations < 1:
            raise ValueError("max_observations must be a positive integer")

        self._max_observations = max_observations
        self._observations: deque[ExecutionObservation] = deque(maxlen=max_observations)
        self._counts: Counter[str] = Counter()
        self._lock = threading.RLock()

    def record(self, observation: ExecutionObservation) -> None:
        with self._lock:
            self._observations.append(observation)
            self._counts[observation.outcome] += 1
            if observation.error_category is not None:
                self._counts[f"error:{observation.error_category}"] += 1

    __call__ = record

    @property
    def observations(self) -> tuple[ExecutionObservation, ...]:
        with self._lock:
            return tuple(self._observations)

    @property
    def recent_observations(self) -> tuple[ExecutionObservation, ...]:
        return self.observations

    @property
    def recent(self) -> tuple[ExecutionObservation, ...]:
        return self.observations

    @property
    def history(self) -> tuple[ExecutionObservation, ...]:
        return self.observations

    @property
    def counts(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)

    def clear(self) -> None:
        with self._lock:
            self._observations.clear()
            self._counts.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._observations)
