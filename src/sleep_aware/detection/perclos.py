"""Time-window PERCLOS calculation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class PerclosWindow:
    window_seconds: float = 60.0
    _observations: deque[tuple[float, bool]] = field(default_factory=deque)

    def update(self, timestamp: float, eyes_closed: bool) -> float:
        self._observations.append((timestamp, eyes_closed))
        cutoff = timestamp - self.window_seconds
        while self._observations and self._observations[0][0] < cutoff:
            self._observations.popleft()
        if not self._observations:
            return 0.0
        return sum(closed for _, closed in self._observations) / len(self._observations)

