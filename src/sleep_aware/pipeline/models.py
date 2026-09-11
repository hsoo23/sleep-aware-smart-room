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
    """Six ordered landmarks for each eye, or no object when no face is found."""

    left_eye: tuple[Point, Point, Point, Point, Point, Point]
    right_eye: tuple[Point, Point, Point, Point, Point, Point]


@dataclass(frozen=True)
class ActionResult:
    """Outcome of one requested device or media action."""

    action: Action
    succeeded: bool
    detail: str | None = None


@dataclass(frozen=True)
class PipelineEvent:
    """Complete, loggable result of processing a single frame."""

    frame_sequence: int
    timestamp: float
    ear: float | None
    state: DrowsinessState
    actions: tuple[Action, ...]
    action_results: tuple[ActionResult, ...]
