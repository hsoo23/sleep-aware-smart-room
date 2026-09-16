"""Structural interfaces implemented by runtime adapters and test fakes."""

from __future__ import annotations

from typing import Protocol

from sleep_aware.control import Action
from sleep_aware.detection import DrowsinessState

from .models import ActionResult, EyeLandmarks, Frame, PipelineEvent


class FrameSource(Protocol):
    """Supply frames until ``read`` returns ``None``."""

    def read(self) -> Frame | None: ...


class LandmarkProcessor(Protocol):
    """Extract ordered eye landmarks; return ``None`` when no face is visible."""

    def process(self, frame: Frame) -> EyeLandmarks | None: ...


class DrowsinessDetector(Protocol):
    """Classify a timestamped EAR observation."""

    @property
    def ear_threshold(self) -> float | None:
        """Threshold applied by the latest update, or ``None`` before one is available."""
        ...

    def update(self, timestamp: float, ear: float | None) -> DrowsinessState: ...


class ActionExecutor(Protocol):
    """Execute one policy action and report its outcome."""

    def execute(self, action: Action) -> ActionResult: ...


class EventLogger(Protocol):
    """Persist or publish one completed frame event."""

    def log(self, event: PipelineEvent) -> None: ...
