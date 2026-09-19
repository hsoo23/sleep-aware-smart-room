"""Hardware-free integration checks for the HTTP action path against the loopback stub."""

from __future__ import annotations

import pytest

from sleep_aware.adapters import ACTION_ENDPOINTS, RaspberryPiHttpActionExecutor
from sleep_aware.adapters.pi_stub_server import SERVED_ENDPOINTS, PiStubServer
from sleep_aware.capture import FakeFrameSource
from sleep_aware.control import Action, ClosedLoopPolicy, Intention
from sleep_aware.detection import TemporalDrowsinessDetector
from sleep_aware.pipeline import BaselinePipeline, EyeLandmarks, Frame, Point


@pytest.fixture
def stub():
    with PiStubServer(port=0) as server:
        yield server


def _executor(base_url: str, **overrides) -> RaspberryPiHttpActionExecutor:
    return RaspberryPiHttpActionExecutor(
        base_url=base_url, timeout_seconds=5.0, allow_insecure_http=True, **overrides
    )


def test_every_action_reaches_the_stub_and_changes_its_state(stub):
    with _executor(stub.base_url) as executor:
        results = [executor.execute(action) for action in Action]

    assert all(result.succeeded for result in results)
    assert {result.status_code for result in results} == {200}
    assert stub.executor.history == list(Action)
    assert stub.state.buzzer_alert_count == 1


def test_repeated_state_commands_keep_the_same_stub_state(stub):
    with _executor(stub.base_url) as executor:
        for _ in range(3):
            executor.execute(Action.LIGHT_OFF)
            executor.execute(Action.PAUSE_MEDIA)

    assert stub.state.light_on is False
    assert stub.state.media_playing is False


def test_non_success_status_is_reported_as_http_status():
    with PiStubServer(port=0, failing_actions=frozenset({Action.LIGHT_ON})) as stub:
        with _executor(stub.base_url) as executor:
            failure = executor.execute(Action.LIGHT_ON)
            recovered = executor.execute(Action.LIGHT_OFF)

    assert (failure.succeeded, failure.error_reason, failure.status_code) == (
        False,
        "http_status",
        503,
    )
    assert recovered.succeeded


def test_stopped_service_is_reported_as_connection_error():
    stub = PiStubServer(port=0).start()
    base_url = stub.base_url
    stub.close()

    with _executor(base_url) as executor:
        result = executor.execute(Action.BUZZER_ALERT)

    assert (result.succeeded, result.error_reason) == (False, "connection_error")


def test_unknown_endpoint_is_not_reported_as_success(stub):
    endpoints = dict(ACTION_ENDPOINTS) | {Action.LIGHT_ON: "/actions/light/unknown"}
    with _executor(stub.base_url, endpoints=endpoints) as executor:
        result = executor.execute(Action.LIGHT_ON)

    assert (result.succeeded, result.error_reason, result.status_code) == (
        False,
        "http_status",
        404,
    )


def test_stub_rejects_invalid_failure_status():
    with pytest.raises(ValueError, match="valid HTTP status code"):
        PiStubServer(port=0, failure_status=99)


@pytest.mark.parametrize("status", [200, 204, 299])
def test_stub_rejects_success_status_for_failure_rehearsal(status):
    # The executor treats any 2xx as success, so a 2xx would hide the rehearsal.
    with pytest.raises(ValueError, match="2xx"):
        PiStubServer(port=0, failure_status=status)


def test_stub_endpoints_match_the_client_contract():
    # Declared separately in both modules; drift must fail here rather than pass silently.
    assert SERVED_ENDPOINTS == {path: action for action, path in ACTION_ENDPOINTS.items()}
    assert len(SERVED_ENDPOINTS) == len(ACTION_ENDPOINTS) == len(Action)


def test_closed_loop_pipeline_drives_the_stub_over_http(stub):
    frames = [Frame(sequence, timestamp, opening) for sequence, (timestamp, opening) in enumerate(
        [(0.0, 0.6), (1.0, 0.2), (3.0, 0.2), (3.5, 0.6), (4.0, 0.6)]
    )]

    class ScriptedLandmarks:
        def process(self, frame):
            opening = frame.payload
            eye = (
                Point(0, 0),
                Point(1, opening),
                Point(3, opening),
                Point(4, 0),
                Point(3, -opening),
                Point(1, -opening),
            )
            return EyeLandmarks(eye, eye)

    class InMemoryEventLogger:
        def __init__(self):
            self.events = []

        def log(self, event):
            self.events.append(event)

    with _executor(stub.base_url) as executor:
        pipeline = BaselinePipeline(
            frame_source=FakeFrameSource(frames),
            landmark_processor=ScriptedLandmarks(),
            detector=TemporalDrowsinessDetector(ear_threshold=0.21, drowsy_seconds=2.0),
            policy=ClosedLoopPolicy(),
            action_executor=executor,
            event_logger=InMemoryEventLogger(),
            intention=Intention.WAKE,
        )
        events = list(pipeline.run())
        pipeline.close()

    assert [action for event in events for action in event.actions] == [
        Action.PAUSE_MEDIA,
        Action.LIGHT_ON,
        Action.BUZZER_ALERT,
        Action.PLAY_MEDIA,
    ]
    assert all(result.succeeded for event in events for result in event.action_results)
    assert stub.state.light_on is True
    assert stub.state.media_playing is True
    assert stub.state.buzzer_alert_count == 1
