"""Deterministic frame source for pipeline tests and hardware-free examples."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from sleep_aware.pipeline.models import Frame


class FakeFrameSource:
    """Return a finite, pre-built sequence of frames."""

    def __init__(self, frames: Iterable[Frame]) -> None:
        self._frames = deque(frames)

    def read(self) -> Frame | None:
        return self._frames.popleft() if self._frames else None
