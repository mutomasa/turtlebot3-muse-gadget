"""Thread-safe store of the latest sample per topic, with receive metrics."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

RATE_SMOOTHING = 0.2  # EWMA weight of the newest inter-arrival interval


@dataclass
class TopicStats:
    count: int = 0
    last_received_s: float | None = None
    mean_interval_s: float | None = None

    def update(self, now: float) -> None:
        if self.last_received_s is not None:
            interval = max(0.0, now - self.last_received_s)
            if self.mean_interval_s is None:
                self.mean_interval_s = interval
            else:
                self.mean_interval_s += RATE_SMOOTHING * (interval - self.mean_interval_s)
        self.count += 1
        self.last_received_s = now

    def snapshot(self, now: float) -> dict[str, Any]:
        age = None if self.last_received_s is None else round(max(0.0, now - self.last_received_s), 3)
        rate = None
        if self.mean_interval_s:
            rate = round(1.0 / self.mean_interval_s, 2)
        return {"count": self.count, "age_s": age, "rate_hz": rate}


class TopicMonitor:
    """Keeps the latest converted message per key (freshness reflects the last receipt)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._samples: dict[str, Any] = {}
        self._stats: dict[str, TopicStats] = {}
        self._started_s = clock()

    def callback(self, key: str, convert: Callable[[Any, float], Any]) -> Callable[[Any], None]:
        def _on_message(msg: Any) -> None:
            now = self._clock()
            self.record(key, convert(msg, now), now)

        return _on_message

    def record(self, key: str, sample: Any, now: float) -> None:
        with self._lock:
            self._samples[key] = sample
            self._stats.setdefault(key, TopicStats()).update(now)

    def watch(self, *keys: str) -> None:
        """Register keys so they appear in metrics even before the first message."""
        with self._lock:
            for key in keys:
                self._stats.setdefault(key, TopicStats())

    def has(self, *keys: str) -> bool:
        with self._lock:
            return all(k in self._samples for k in keys)

    def get(self, key: str) -> Any:
        with self._lock:
            return self._samples.get(key)

    def metrics(self) -> dict[str, Any]:
        now = self._clock()
        with self._lock:
            topics = {key: stats.snapshot(now) for key, stats in sorted(self._stats.items())}
        return {"uptime_s": round(now - self._started_s, 1), "topics": topics}
