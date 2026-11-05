"""Hardware-free checks for the Raspberry Pi service; GPIO is a fake, not a relay or buzzer."""

from __future__ import annotations

import threading

import pytest
import requests

from sleep_aware.adapters import ACTION_ENDPOINTS, RaspberryPiHttpActionExecutor
from sleep_aware.adapters.pi_service import PiActionService
from sleep_aware.capture import FakeFrameSource
from sleep_aware.control import Action, ClosedLoopPolicy, Intention
from sleep_aware.detection import TemporalDrowsinessDetector
from sleep_aware.pipeline import BaselinePipeline, EyeLandmarks, Frame, Point


class FakeGpio:
    BCM = "BCM"
    OUT = "OUT"
    IN = "IN"
    LOW = 0
    HIGH = 1
    PUD_OFF = "PUD_OFF"

    def __init__(self):
        self.calls = []

    def setmode(self, mode):
        self.calls.append(("setmode", mode))

    def setup(self, pin, mode, **kwargs):
        self.calls.append(("setup", pin, mode))

    def output(self, pin, value):
        self.calls.append(("output", pin, value))

    def cleanup(self, pins):
        self.calls.append(("cleanup", pins))


@pytest.fixture
def gpio():
    return FakeGpio()


@pytest.fixture
def service(gpio):
    with PiActionService(gpio=gpio, port=0, alert_pattern=(0.0, 0.0)) as running:
        yield running


def _post(service: PiActionService, action: Action) -> requests.Response:
    url = f"http://127.0.0.1:{service.port}{ACTION_ENDPOINTS[action]}"
    return requests.post(url, timeout=5)


def _wait_for_alert(service: PiActionService) -> None:
    service._alert_thread.join(timeout=5)


def test_start_turns_the_active_low_lamp_on(service, gpio):
    assert ("setup", 17, gpio.OUT) in gpio.calls
    assert ("output", 17, gpio.LOW) in gpio.calls


def test_light_endpoints_drive_the_relay_and_can_repeat(service, gpio):
    gpio.calls.clear()

    assert _post(service, Action.LIGHT_OFF).status_code == 200
    assert _post(service, Action.LIGHT_OFF).status_code == 200
    assert gpio.calls == [("setup", 17, gpio.IN)] * 2

    gpio.calls.clear()
    assert _post(service, Action.LIGHT_ON).status_code == 200
    assert gpio.calls == [("setup", 17, gpio.OUT), ("output", 17, gpio.LOW)]


@pytest.mark.parametrize("action", [Action.START_SESSION, Action.END_SESSION])
def test_session_endpoints_succeed_without_touching_gpio(service, gpio, action):
    gpio.calls.clear()

    assert _post(service, action).status_code == 200
    assert gpio.calls == []


@pytest.mark.parametrize("action", [Action.PAUSE_MEDIA, Action.PLAY_MEDIA])
def test_media_endpoints_state_that_nothing_physical_happened(service, gpio, action, caplog):
    gpio.calls.clear()

    response = _post(service, action)

    assert response.status_code == 200
    assert response.json()["physical"] is False
    assert gpio.calls == []
    assert "media_not_connected" in caplog.text


def test_buzzer_response_does_not_wait_for_the_alert(gpio):
    release = threading.Event()
    original_output = gpio.output

    def blocking_output(pin, value):
        if value == gpio.HIGH:
            release.wait(timeout=5)
        original_output(pin, value)

    gpio.output = blocking_output
    with PiActionService(gpio=gpio, port=0, alert_pattern=(0.0, 0.0)) as service:
        try:
            # Answering while the first HIGH is still blocked proves the response is
            # independent of the alert length, which exceeds the client timeout.
            assert _post(service, Action.BUZZER_ALERT).status_code == 202
            assert ("output", 18, gpio.HIGH) not in gpio.calls
        finally:
            release.set()


def test_buzzer_requests_inside_the_window_alert_once(gpio):
    now = [100.0]
    with PiActionService(
        gpio=gpio, port=0, alert_pattern=(0.0, 0.0), clock=lambda: now[0]
    ) as service:
        assert _post(service, Action.BUZZER_ALERT).status_code == 202
        _wait_for_alert(service)

        repeated = _post(service, Action.BUZZER_ALERT)
        assert repeated.status_code == 200
        assert repeated.json()["deduplicated"] is True
        assert gpio.calls.count(("output", 18, gpio.HIGH)) == 1

        now[0] += 5.0
        assert _post(service, Action.BUZZER_ALERT).status_code == 202
        _wait_for_alert(service)
        assert gpio.calls.count(("output", 18, gpio.HIGH)) == 2


def test_gpio_failure_is_reported_as_a_server_error(service, gpio):
    def failing_setup(*_args, **_kwargs):
        raise RuntimeError("simulated GPIO failure")

    working_setup = gpio.setup
    gpio.setup = failing_setup
    try:
        response = _post(service, Action.LIGHT_OFF)
    finally:
        gpio.setup = working_setup  # The fixture still has to release the pins.

    assert response.status_code == 500
    assert response.json()["error_reason"].startswith("gpio_error")


def test_unknown_path_and_get_are_rejected(service):
    base_url = f"http://127.0.0.1:{service.port}"

    assert requests.post(f"{base_url}/actions/light/unknown", timeout=5).status_code == 404
    assert requests.get(f"{base_url}/actions/light/on", timeout=5).status_code == 405


def test_close_waits_for_the_alert_then_releases_gpio_safely(gpio):
    with PiActionService(gpio=gpio, port=0, alert_pattern=(0.05, 0.05)) as service:
        assert _post(service, Action.BUZZER_ALERT).status_code == 202

    high = gpio.calls.index(("output", 18, gpio.HIGH))
    cleanup = gpio.calls.index(("cleanup", (17, 18)))
    assert high < cleanup
    assert gpio.calls[cleanup - 2:cleanup] == [("output", 18, gpio.LOW), ("setup", 17, gpio.IN)]


def test_gpio_setup_failure_releases_the_port():
    class BrokenGpio(FakeGpio):
        def setmode(self, mode):
            raise RuntimeError("Cannot determine SOC peripheral base address")

    with pytest.raises(RuntimeError, match="SOC"):
        PiActionService(gpio=BrokenGpio(), port=0)


def test_stopped_service_is_reported_as_connection_error(gpio):
    service = PiActionService(gpio=gpio, port=0).start()
    base_url = f"http://127.0.0.1:{service.port}"
    service.close()

    with RaspberryPiHttpActionExecutor(base_url=base_url, timeout_seconds=1.0) as executor:
        result = executor.execute(Action.LIGHT_ON)

    assert (result.succeeded, result.error_reason) == (False, "connection_error")


class _ScriptedLandmarks:
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


class _InMemoryEventLogger:
    def log(self, event):
        pass


def test_closed_loop_runs_over_http_and_finishes_cleanly(service, gpio):
    timeline = [(0.0, 0.6), (1.0, 0.2), (3.0, 0.2), (3.5, 0.6), (4.0, 0.6)]
    frames = [Frame(index, *sample) for index, sample in enumerate(timeline)]
    policy = ClosedLoopPolicy()
    base_url = f"http://127.0.0.1:{service.port}"
    gpio.calls.clear()

    with RaspberryPiHttpActionExecutor(base_url=base_url, timeout_seconds=5.0) as executor:
        pipeline = BaselinePipeline(
            frame_source=FakeFrameSource(frames),
            landmark_processor=_ScriptedLandmarks(),
            detector=TemporalDrowsinessDetector(ear_threshold=0.21, drowsy_seconds=2.0),
            policy=policy,
            action_executor=executor,
            event_logger=_InMemoryEventLogger(),
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
    assert not policy.has_pending_cleanup
    assert ("setup", 17, gpio.OUT) in gpio.calls
