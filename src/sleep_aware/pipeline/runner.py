"""Minimal synchronous orchestration for the fixed-EAR baseline."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from time import perf_counter

from sleep_aware.control import Action, ClosedLoopPolicy, Intention
from sleep_aware.detection import DrowsinessState, calculate_eye_ears

from .contracts import (
    ActionExecutor,
    DrowsinessDetector,
    EventLogger,
    FrameSource,
    LandmarkProcessor,
)
from .models import ActionResult, EyeLandmarks, LatencyBreakdown, PipelineEvent

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
        clock: Callable[[], float] = time.monotonic,
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
        # Must be the same monotonic clock that stamps Frame.timestamp.
        self._clock = clock
        self._previous_state: DrowsinessState | None = None

    def run(self) -> Iterator[PipelineEvent]:
        """Process all available frames and yield each event after it is logged."""
        self._policy.reset(self._intention)
        while (frame := self._frame_source.read()) is not None:
            inference_start = self._clock()
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
            control_start = self._clock()
            results = tuple(self._execute(action) for action in actions)
            control_end = self._clock()
            event = PipelineEvent(
                frame_sequence=frame.sequence,
                timestamp=frame.timestamp,
                intention=self._intention,
                ear=ear,
                ear_threshold=self._detector.ear_threshold,
                previous_state=self._previous_state,
                state=state,
                actions=actions,
                action_results=results,
                policy_transition=policy_transition,
                latency=LatencyBreakdown(
                    inference=control_start - inference_start,
                    control=control_end - control_start,
                    end_to_end=control_end - frame.timestamp,
                ),
                left_ear=left_ear,
                right_ear=right_ear,
                landmark_latency_ms=landmark_latency_ms,
                inference_latency_ms=inference_latency_ms,
            )
            self._previous_state = state
            self._event_logger.log(event)
            yield event

    def set_intention(self, intention: Intention) -> None:
        """Apply a mode change on the next observation."""
        self._intention = intention

    def _execute(self, action: Action) -> ActionResult:
        start = self._clock()
        try:
            result = self._action_executor.execute(action)
        except Exception as error:  # noqa: BLE001 - keep re-observing after device failures.
            result = ActionResult(action=action, succeeded=False, detail=str(error))
        if result.action is not action:
            raise ValueError(
                f"executor returned result for {result.action.value}, expected {action.value}"
            )
        return replace(result, latency=self._clock() - start)
