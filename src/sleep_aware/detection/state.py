"""Frame-rate-independent temporal drowsiness state logic."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DrowsinessState(str, Enum):
    NO_FACE = "NO_FACE"
    AWAKE = "AWAKE"
    EYES_CLOSED = "EYES_CLOSED"
    DROWSY = "DROWSY"


@dataclass
class TemporalDrowsinessDetector:
    ear_threshold: float = 0.21
    drowsy_seconds: float = 2.0
    recovery_seconds: float = 0.5
    _closed_since: float | None = None
    _open_since: float | None = None
    _state: DrowsinessState = DrowsinessState.NO_FACE

    def update(self, timestamp: float, ear: float | None) -> DrowsinessState:
        if ear is None:
            self._closed_since = None
            self._open_since = None
            self._state = DrowsinessState.NO_FACE
            return self._state

        if ear < self.ear_threshold:
            self._open_since = None
            if self._closed_since is None:
                self._closed_since = timestamp
            elapsed = timestamp - self._closed_since
            self._state = (
                DrowsinessState.DROWSY
                if elapsed >= self.drowsy_seconds
                else DrowsinessState.EYES_CLOSED
            )
            return self._state

        self._closed_since = None
        if self._open_since is None:
            self._open_since = timestamp
        if timestamp - self._open_since >= self.recovery_seconds:
            self._state = DrowsinessState.AWAKE
        return self._state

