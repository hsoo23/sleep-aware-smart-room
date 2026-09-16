"""Minimal synchronous orchestration for the fixed-EAR baseline."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from time import perf_counter

from sleep_aware.control import Action, ClosedLoopPolicy, Intention
from sleep_aware.detection import calculate_eye_ears

from .contracts import (
    ActionExecutor,
    DrowsinessDetector,
    EventLogger,
    FrameSource,
    LandmarkProcessor,
)
from .models import ActionResult, EyeLandmarks, PipelineEvent

EarResult = float | tuple[float, float, float]


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
        ear_calculator: Callable[[EyeLandmarks], EarResult] = calculate_eye_ears,
        latency_clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._frame_source = frame_source
        self._landmark_processor = landmark_processor
        self._detector = detector
        self._policy = policy
        self._action_executor = action_executor
        self._event_logger = event_logger
        self._intention = intention
        self._ear_calculator = ear_calculator
        self._latency_clock = latency_clock

    def run(self) -> Iterator[PipelineEvent]:
        """Process all available frames and yield each event after it is logged."""
        self._policy.reset(self._intention)
        while (frame := self._frame_source.read()) is not None:
            landmark_started = self._latency_clock()
            landmarks = self._landmark_processor.process(frame)
            landmark_latency_ms = (self._latency_clock() - landmark_started) * 1_000

            inference_started = self._latency_clock()
            left_ear: float | None = None
            right_ear: float | None = None
            ear: float | None = None
            if landmarks is not None:
                ear_result = self._ear_calculator(landmarks)
                if isinstance(ear_result, tuple):
                    left_ear, right_ear, ear = ear_result
                else:
                    ear = ear_result
            state = self._detector.update(frame.timestamp, ear)
            inference_latency_ms = (self._latency_clock() - inference_started) * 1_000
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
                left_ear=left_ear,
                right_ear=right_ear,
                landmark_latency_ms=landmark_latency_ms,
                inference_latency_ms=inference_latency_ms,
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
