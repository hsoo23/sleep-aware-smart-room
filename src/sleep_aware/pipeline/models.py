"""Data transferred across baseline pipeline boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sleep_aware.control import Action, Intention
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
    latency: float | None = None
    """Monotonic seconds spent in ``ActionExecutor.execute``; set by the pipeline."""


@dataclass(frozen=True)
class LatencyBreakdown:
    """Monotonic durations, in seconds, measured while processing one frame.

    ``inference`` spans landmark extraction, EAR calculation, and detection.
    ``control`` spans policy decision and execution of every action.
    ``end_to_end`` spans frame capture (``Frame.timestamp``) to the last action
    result; it excludes event logging.
    """

    inference: float
    control: float
    end_to_end: float


@dataclass(frozen=True)
class PipelineEvent:
    """Complete, loggable result of processing a single frame."""

    frame_sequence: int
    timestamp: float
    intention: Intention
    ear: float | None
    ear_threshold: float | None
    previous_state: DrowsinessState | None
    state: DrowsinessState
    actions: tuple[Action, ...]
    action_results: tuple[ActionResult, ...]
    latency: LatencyBreakdown

    @property
    def state_changed(self) -> bool:
        """Whether this frame changed the detected state; the first frame always does."""
        return self.previous_state is not self.state
