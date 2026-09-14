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
