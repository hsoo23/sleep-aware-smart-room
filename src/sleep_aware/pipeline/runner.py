"""Minimal synchronous orchestration for the fixed-EAR baseline."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import numpy as np

from sleep_aware.control import Action, ClosedLoopPolicy, Intention
from sleep_aware.detection import calculate_ear

from .contracts import (
    ActionExecutor,
    DrowsinessDetector,
    EventLogger,
    FrameSource,
    LandmarkProcessor,
)
from .models import ActionResult, EyeLandmarks, PipelineEvent, Point


def _eye_array(points: tuple[Point, Point, Point, Point, Point, Point]) -> np.ndarray:
    return np.asarray([(point.x, point.y) for point in points], dtype=float)


def _mean_ear(landmarks: EyeLandmarks) -> float:
    left = calculate_ear(_eye_array(landmarks.left_eye))
    right = calculate_ear(_eye_array(landmarks.right_eye))
    return (left + right) / 2.0


class BaselinePipeline:
    """Connect replaceable input/output adapters to pure detection and policy."""

    def __init__(
        self,
        *,
        frame_source: FrameSource,
        landmark_processor: LandmarkProcessor,
        detector: DrowsinessDetector,
        policy: ClosedLoopPolicy,
        action_executor: ActionExecutor,
        event_logger: EventLogger,
        intention: Intention,
        ear_calculator: Callable[[EyeLandmarks], float] = _mean_ear,
    ) -> None:
        self._frame_source = frame_source
        self._landmark_processor = landmark_processor
        self._detector = detector
        self._policy = policy
        self._action_executor = action_executor
        self._event_logger = event_logger
        self._intention = intention
        self._ear_calculator = ear_calculator

    def run(self) -> Iterator[PipelineEvent]:
        """Process all available frames and yield each event after it is logged."""
        self._policy.reset(self._intention)
        while (frame := self._frame_source.read()) is not None:
            landmarks = self._landmark_processor.process(frame)
            ear = self._ear_calculator(landmarks) if landmarks is not None else None
            state = self._detector.update(frame.timestamp, ear)
            policy_transition = self._policy.transition(self._intention, state)
            actions = policy_transition.actions
            results = tuple(self._execute(action) for action in actions)
            event = PipelineEvent(
                frame_sequence=frame.sequence,
                timestamp=frame.timestamp,
                ear=ear,
                state=state,
                actions=actions,
                action_results=results,
                policy_transition=policy_transition,
            )
            self._event_logger.log(event)
            yield event

    def set_intention(self, intention: Intention) -> None:
        """Apply a mode change on the next observation."""
        self._intention = intention

    def _execute(self, action: Action) -> ActionResult:
        try:
            result = self._action_executor.execute(action)
        except Exception as error:  # Device failures must not stop re-observation.
            return ActionResult(action=action, succeeded=False, detail=str(error))
        if result.action is not action:
            raise ValueError(
                f"executor returned result for {result.action.value}, expected {action.value}"
            )
        return result
