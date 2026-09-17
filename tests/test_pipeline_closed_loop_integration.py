"""End-to-end closed-loop runs using fake adapters and the real detector and policy."""

from collections import deque

import pytest

from sleep_aware.control import Action, ClosedLoopPolicy, Intention
from sleep_aware.detection import DrowsinessState, TemporalDrowsinessDetector
from sleep_aware.pipeline import ActionResult, BaselinePipeline, EyeLandmarks, Frame, Point

OPEN = 0.6  # EAR = 0.3
CLOSED = 0.2  # EAR = 0.1

# (timestamp, eye opening or None for no face). Open -> closed for 2 s -> recovered.
CLOSED_LOOP_SCRIPT = [
    (0.0, OPEN),
    (0.5, OPEN),
    (1.0, CLOSED),
    (2.0, CLOSED),
    (3.0, CLOSED),
    (3.2, OPEN),
    (3.7, OPEN),
]


def _eye(opening: float) -> tuple[Point, Point, Point, Point, Point, Point]:
    return (
        Point(0, 0),
        Point(1, opening),
        Point(3, opening),
        Point(4, 0),
        Point(3, -opening),
        Point(1, -opening),
    )


class ScriptedCamera:
    """Frame source and landmark processor driven by one observation script."""

    def __init__(self, script: list[tuple[float, float | None]]) -> None:
        self._frames = deque(
            Frame(sequence, timestamp, opening)
            for sequence, (timestamp, opening) in enumerate(script)
        )

    def read(self) -> Frame | None:
        return self._frames.popleft() if self._frames else None

    def process(self, frame: Frame) -> EyeLandmarks | None:
        if frame.payload is None:
            return None
        return EyeLandmarks(_eye(frame.payload), _eye(frame.payload))


class RecordingExecutor:
    def __init__(self, unsuccessful: set[Action] | None = None) -> None:
        self.executed: list[Action] = []
        self._unsuccessful = unsuccessful or set()

    def execute(self, action: Action) -> ActionResult:
        self.executed.append(action)
        if action in self._unsuccessful:
            return ActionResult(action=action, succeeded=False, detail="relay offline")
        return ActionResult(action=action, succeeded=True)


class WrongActionExecutor:
    def execute(self, action: Action) -> ActionResult:
        return ActionResult(action=Action.LIGHT_ON, succeeded=True)


class InMemoryEventLogger:
    def __init__(self) -> None:
        self.events = []

    def log(self, event) -> None:
        self.events.append(event)


def _pipeline(script, intention, executor=None, logger=None) -> BaselinePipeline:
    camera = ScriptedCamera(script)
    return BaselinePipeline(
        frame_source=camera,
        landmark_processor=camera,
        detector=TemporalDrowsinessDetector(
            ear_threshold=0.21, drowsy_seconds=2.0, recovery_seconds=0.5
        ),
        policy=ClosedLoopPolicy(),
        action_executor=executor or RecordingExecutor(),
        event_logger=logger or InMemoryEventLogger(),
        intention=intention,
    )


def _actions_by_state(events) -> list[tuple[DrowsinessState, tuple[Action, ...]]]:
    return [(event.state, event.actions) for event in events if event.actions]


def test_pipeline_sleep_mode_runs_detect_actuate_reobserve_restore_loop():
    executor = RecordingExecutor()
    events = list(_pipeline(CLOSED_LOOP_SCRIPT, Intention.SLEEP, executor).run())

    assert [event.state for event in events[1:]] == [
        DrowsinessState.AWAKE,
        DrowsinessState.EYES_CLOSED,
        DrowsinessState.EYES_CLOSED,
        DrowsinessState.DROWSY,
        DrowsinessState.DROWSY,
        DrowsinessState.AWAKE,
    ]
    assert _actions_by_state(events) == [
        (
            DrowsinessState.DROWSY,
            (Action.PAUSE_MEDIA, Action.LIGHT_OFF, Action.START_SESSION),
        ),
        (DrowsinessState.AWAKE, (Action.END_SESSION,)),
    ]
    assert executor.executed == [
        Action.PAUSE_MEDIA,
        Action.LIGHT_OFF,
        Action.START_SESSION,
        Action.END_SESSION,
    ]


def test_pipeline_wake_mode_resumes_media_after_recovery():
    executor = RecordingExecutor()
    events = list(_pipeline(CLOSED_LOOP_SCRIPT, Intention.WAKE, executor).run())

    assert _actions_by_state(events) == [
        (
            DrowsinessState.DROWSY,
            (Action.PAUSE_MEDIA, Action.LIGHT_ON, Action.BUZZER_ALERT),
        ),
        (DrowsinessState.AWAKE, (Action.PLAY_MEDIA,)),
    ]
    assert executor.executed == [
        action for _, actions in _actions_by_state(events) for action in actions
    ]


def test_pipeline_unsuccessful_action_result_is_logged_and_loop_continues():
    executor = RecordingExecutor(unsuccessful={Action.BUZZER_ALERT})
    logger = InMemoryEventLogger()
    events = list(_pipeline(CLOSED_LOOP_SCRIPT, Intention.WAKE, executor, logger).run())

    drowsy_event = next(event for event in events if event.actions)
    buzzer = drowsy_event.action_results[2]
    assert (buzzer.action, buzzer.succeeded, buzzer.detail) == (
        Action.BUZZER_ALERT,
        False,
        "relay offline",
    )
    assert events[-1].actions == (Action.PLAY_MEDIA,)
    assert logger.events == events


def test_pipeline_no_face_while_drowsy_does_not_repeat_actions():
    script = [
        (0.0, CLOSED),
        (2.0, CLOSED),
        (2.2, None),
        (2.4, CLOSED),
        (4.4, CLOSED),
        (4.6, OPEN),
        (5.1, OPEN),
    ]
    executor = RecordingExecutor()
    events = list(_pipeline(script, Intention.SLEEP, executor).run())

    assert [event.state for event in events] == [
        DrowsinessState.EYES_CLOSED,
        DrowsinessState.DROWSY,
        DrowsinessState.NO_FACE,
        DrowsinessState.EYES_CLOSED,
        DrowsinessState.DROWSY,
        DrowsinessState.DROWSY,
        DrowsinessState.AWAKE,
    ]
    assert executor.executed == [
        Action.PAUSE_MEDIA,
        Action.LIGHT_OFF,
        Action.START_SESSION,
        Action.END_SESSION,
    ]


def test_pipeline_logs_each_event_before_yielding_it():
    logger = InMemoryEventLogger()
    run = _pipeline(CLOSED_LOOP_SCRIPT, Intention.SLEEP, logger=logger).run()

    for expected_count, event in enumerate(run, start=1):
        assert len(logger.events) == expected_count
        assert logger.events[-1] is event


def test_pipeline_executor_result_for_wrong_action_is_a_contract_violation():
    run = _pipeline(CLOSED_LOOP_SCRIPT, Intention.SLEEP, executor=WrongActionExecutor()).run()

    with pytest.raises(ValueError, match="expected pause_media"):
        list(run)
