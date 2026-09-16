"""Data transferred across baseline pipeline boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sleep_aware.control import Action
from sleep_aware.detection import DrowsinessState


@dataclass(frozen=True)
class Point:
    """A normalized or pixel-space 2-D landmark coordinate."""

    x: float
    y: float


@dataclass(frozen=True)
class Frame:
    """One captured frame and its monotonic capture timestamp."""

    sequence: int
    timestamp: float
    payload: Any


@dataclass(frozen=True)
class EyeLandmarks:
    """Face mesh and six ordered landmarks for each eye."""

    left_eye: tuple[Point, Point, Point, Point, Point, Point]
    right_eye: tuple[Point, Point, Point, Point, Point, Point]
    face_landmarks: tuple[Point, ...] = ()


@dataclass(frozen=True)
class ActionResult:
    """Outcome of one requested device or media action."""

    action: Action
    succeeded: bool
    detail: str | None = None
    elapsed_ms: float | None = None
    error_reason: str | None = None
    status_code: int | None = None


@dataclass(frozen=True)
class PipelineEvent:
    """Complete, loggable result of processing a single frame."""

    frame_sequence: int
    timestamp: float
    ear: float | None
    state: DrowsinessState
    actions: tuple[Action, ...]
    action_results: tuple[ActionResult, ...]
    left_ear: float | None = None
    right_ear: float | None = None
    landmark_latency_ms: float = 0.0
    inference_latency_ms: float = 0.0
