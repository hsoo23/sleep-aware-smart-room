from collections import deque

import pytest

from sleep_aware.control import Action, ClosedLoopPolicy, Intention
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


class FakeFrameSource:
    def __init__(self, frames: list[Frame]) -> None:
        self.frames = deque(frames)

    def read(self) -> Frame | None:
        return self.frames.popleft() if self.frames else None


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
