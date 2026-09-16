from __future__ import annotations

from collections import deque

import pytest

from sleep_aware.capture import FakeFrameSource
from sleep_aware.control import (
    Action,
    ClosedLoopPolicy,
    Intention,
    PolicyPhase,
    TransitionReason,
)
from sleep_aware.detection import DrowsinessState, TemporalDrowsinessDetector
from sleep_aware.pipeline import ActionResult, BaselinePipeline, EyeLandmarks, Frame, Point


def _eye(vertical: float) -> tuple[Point, Point, Point, Point, Point, Point]:
    return (
        Point(0, 0),
        Point(1, vertical),
        Point(3, vertical),
        Point(4, 0),
        Point(3, -vertical),
        Point(1, -vertical),
    )


class FakeLandmarkProcessor:
    def __init__(self, observations: list[EyeLandmarks | None]) -> None:
        self.observations = deque(observations)

    def process(self, frame: Frame) -> EyeLandmarks | None:
        return self.observations.popleft()


class FakeActionExecutor:
    def __init__(self, failing_action: Action | None = None) -> None:
        self.executed: list[Action] = []
        self.failing_action = failing_action

    def execute(self, action: Action) -> ActionResult:
        self.executed.append(action)
        if action is self.failing_action:
            raise OSError("device unavailable")
        return ActionResult(action=action, succeeded=True)


class SteppingClock:
    """Monotonic fake clock that advances by ``step`` on every read."""

    def __init__(self, start: float, step: float) -> None:
        self.now = start - step
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


class InMemoryEventLogger:
    def __init__(self) -> None:
        self.events = []

    def log(self, event) -> None:
        self.events.append(event)


def test_fake_pipeline_connects_frames_to_actions_and_results():
    frames = [Frame(0, 0.0, object()), Frame(1, 2.0, object())]
    closed_eye = EyeLandmarks(_eye(0.4), _eye(0.4))  # EAR = 0.2
    executor = FakeActionExecutor(failing_action=Action.LIGHT_ON)
    logger = InMemoryEventLogger()
    pipeline = BaselinePipeline(
        frame_source=FakeFrameSource(frames),
        landmark_processor=FakeLandmarkProcessor([closed_eye, closed_eye]),
        detector=TemporalDrowsinessDetector(ear_threshold=0.21, drowsy_seconds=2.0),
        policy=ClosedLoopPolicy(),
        action_executor=executor,
        event_logger=logger,
        intention=Intention.WAKE,
        clock=SteppingClock(start=2.5, step=0.25),
    )

    events = list(pipeline.run())

    assert [event.state for event in events] == [
        DrowsinessState.EYES_CLOSED,
        DrowsinessState.DROWSY,
    ]
    assert events[0].ear == pytest.approx(0.2)
    assert events[1].actions == (
        Action.PAUSE_MEDIA,
        Action.LIGHT_ON,
        Action.BUZZER_ALERT,
    )
    assert [result.succeeded for result in events[1].action_results] == [True, False, True]
    assert events[1].action_results[1].detail == "device unavailable"
    assert events[1].policy_transition.previous_phase is PolicyPhase.IDLE
    assert events[1].policy_transition.next_phase is PolicyPhase.AWAITING_RECOVERY
    assert events[1].policy_transition.reason is TransitionReason.DROWSY_DETECTED
    assert executor.executed == list(events[1].actions)
    assert logger.events == events


def test_events_record_intention_threshold_and_state_transitions():
    frames = [Frame(0, 0.0, object()), Frame(1, 2.0, object())]
    closed_eye = EyeLandmarks(_eye(0.4), _eye(0.4))
    pipeline = BaselinePipeline(
        frame_source=FakeFrameSource(frames),
        landmark_processor=FakeLandmarkProcessor([closed_eye, closed_eye]),
        detector=TemporalDrowsinessDetector(ear_threshold=0.21, drowsy_seconds=2.0),
        policy=ClosedLoopPolicy(),
        action_executor=FakeActionExecutor(),
        event_logger=InMemoryEventLogger(),
        intention=Intention.SLEEP,
        clock=SteppingClock(start=2.5, step=0.25),
    )

    first, second = pipeline.run()

    assert first.intention is Intention.SLEEP
    assert first.ear_threshold == pytest.approx(0.21)
    assert first.previous_state is None
    assert first.state_changed
    assert second.previous_state is DrowsinessState.EYES_CLOSED
    assert second.state_changed


def test_latency_uses_monotonic_clock_for_each_stage_and_action():
    frames = [Frame(0, 10.0, object()), Frame(1, 12.0, object())]
    closed_eye = EyeLandmarks(_eye(0.4), _eye(0.4))
    pipeline = BaselinePipeline(
        frame_source=FakeFrameSource(frames),
        landmark_processor=FakeLandmarkProcessor([closed_eye, closed_eye]),
        detector=TemporalDrowsinessDetector(ear_threshold=0.21, drowsy_seconds=2.0),
        policy=ClosedLoopPolicy(),
        action_executor=FakeActionExecutor(failing_action=Action.LIGHT_ON),
        event_logger=InMemoryEventLogger(),
        intention=Intention.WAKE,
        clock=SteppingClock(start=12.5, step=0.25),
    )

    first, second = pipeline.run()

    # Frame 0 reads the clock three times: 12.5, 12.75, 13.0.
    assert first.latency.inference == pytest.approx(0.25)
    assert first.latency.control == pytest.approx(0.25)
    assert first.latency.end_to_end == pytest.approx(3.0)
    # Frame 1: inference 13.25 -> 13.5, three actions of 0.25 s each, control end 15.25.
    assert second.latency.inference == pytest.approx(0.25)
    assert [result.latency for result in second.action_results] == pytest.approx([0.25] * 3)
    assert second.action_results[1].succeeded is False
    assert second.latency.control == pytest.approx(1.75)
    assert second.latency.end_to_end == pytest.approx(3.25)


def test_no_face_is_forwarded_as_missing_ear():
    logger = InMemoryEventLogger()
    pipeline = BaselinePipeline(
        frame_source=FakeFrameSource([Frame(7, 10.0, object())]),
        landmark_processor=FakeLandmarkProcessor([None]),
        detector=TemporalDrowsinessDetector(),
        policy=ClosedLoopPolicy(),
        action_executor=FakeActionExecutor(),
        event_logger=logger,
        intention=Intention.SLEEP,
    )

    event = next(pipeline.run())

    assert event.frame_sequence == 7
    assert event.ear is None
    assert event.state is DrowsinessState.NO_FACE
    assert event.actions == ()
    assert event.action_results == ()
    assert event.policy_transition.reason is TransitionReason.NO_FACE_IGNORED


def test_pipeline_records_ear_components_and_processing_latencies():
    times = iter((1.0, 1.012, 2.0, 2.003))
    open_eye = EyeLandmarks(_eye(0.6), _eye(0.4))
    pipeline = BaselinePipeline(
        frame_source=FakeFrameSource([Frame(0, 0.0, object())]),
        landmark_processor=FakeLandmarkProcessor([open_eye]),
        detector=TemporalDrowsinessDetector(),
        policy=ClosedLoopPolicy(),
        action_executor=FakeActionExecutor(),
        event_logger=InMemoryEventLogger(),
        intention=Intention.WAKE,
        latency_clock=lambda: next(times),
    )

    event = next(pipeline.run())

    assert event.left_ear == pytest.approx(0.3)
    assert event.right_ear == pytest.approx(0.2)
    assert event.ear == pytest.approx(0.25)
    assert event.landmark_latency_ms == pytest.approx(12.0)
    assert event.inference_latency_ms == pytest.approx(3.0)


def test_pipeline_start_cleans_up_reused_policy_state():
    policy = ClosedLoopPolicy()
    policy.decide(Intention.WAKE, DrowsinessState.DROWSY)
    logger = InMemoryEventLogger()
    pipeline = BaselinePipeline(
        frame_source=FakeFrameSource([Frame(0, 1.0, object())]),
        landmark_processor=FakeLandmarkProcessor([EyeLandmarks(_eye(1.0), _eye(1.0))]),
        detector=TemporalDrowsinessDetector(recovery_seconds=0.0),
        policy=policy,
        action_executor=FakeActionExecutor(),
        event_logger=logger,
        intention=Intention.WAKE,
    )

    event = next(pipeline.run())

    assert event.state is DrowsinessState.AWAKE
    assert event.actions == (Action.PLAY_MEDIA,)
    assert event.policy_transition.reason is TransitionReason.RESET
    assert event.policy_transition.previous_phase is PolicyPhase.AWAITING_RECOVERY
    assert event.policy_transition.next_phase is PolicyPhase.IDLE


def test_pipeline_close_restores_policy_owned_resources():
    executor = FakeActionExecutor(failing_action=Action.LIGHT_ON)
    closed_eye = EyeLandmarks(_eye(0.4), _eye(0.4))
    pipeline = BaselinePipeline(
        frame_source=FakeFrameSource([Frame(0, 0.0, object()), Frame(1, 2.0, object())]),
        landmark_processor=FakeLandmarkProcessor([closed_eye, closed_eye]),
        detector=TemporalDrowsinessDetector(ear_threshold=0.21, drowsy_seconds=2.0),
        policy=ClosedLoopPolicy(),
        action_executor=executor,
        event_logger=InMemoryEventLogger(),
        intention=Intention.WAKE,
    )

    list(pipeline.run())
    results = pipeline.close()

    assert [result.action for result in results] == [Action.PLAY_MEDIA]
    assert executor.executed[-1] is Action.PLAY_MEDIA


def test_pipeline_close_retries_cleanup_without_losing_pending_state():
    class FlakyCleanupExecutor(FakeActionExecutor):
        def __init__(self) -> None:
            super().__init__()
            self.play_attempts = 0

        def execute(self, action: Action) -> ActionResult:
            self.executed.append(action)
            if action is Action.PLAY_MEDIA:
                self.play_attempts += 1
                return ActionResult(action=action, succeeded=self.play_attempts >= 3)
            return ActionResult(action=action, succeeded=True)

    executor = FlakyCleanupExecutor()
    policy = ClosedLoopPolicy()
    policy.transition(Intention.WAKE, DrowsinessState.DROWSY)
    pipeline = BaselinePipeline(
        frame_source=FakeFrameSource([]),
        landmark_processor=FakeLandmarkProcessor([]),
        detector=TemporalDrowsinessDetector(),
        policy=policy,
        action_executor=executor,
        event_logger=InMemoryEventLogger(),
        intention=Intention.WAKE,
    )

    first = pipeline.close(max_attempts=2)
    second = pipeline.close(max_attempts=2)
    third = pipeline.close(max_attempts=2)

    assert [result.succeeded for result in first] == [False, False]
    assert [result.succeeded for result in second] == [True]
    assert third == ()
