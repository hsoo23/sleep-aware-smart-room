from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest

from sleep_aware.adapters import (
    CompositeActionExecutor,
    MacOSChromeMediaActionExecutor,
    RaspberryPiGpioActionExecutor,
    SessionActionExecutor,
)
from sleep_aware.control import Action
from sleep_aware.pipeline.models import ActionResult


def ticking_clock(*values: float):
    times = iter(values)
    return lambda: next(times)


def test_media_adapter_reports_unsupported_platform_without_running_process():
    called = False

    def runner(*_args, **_kwargs):
        nonlocal called
        called = True

    executor = MacOSChromeMediaActionExecutor(
        system="Linux", runner=runner, clock=ticking_clock(1.0, 1.01)
    )

    result = executor.execute(Action.PAUSE_MEDIA)

    assert not result.succeeded
    assert result.error_reason == "unsupported_platform"
    assert not called


@pytest.mark.parametrize(
    ("action", "output"),
    [(Action.PAUSE_MEDIA, "pause\n"), (Action.PLAY_MEDIA, "play\n")],
)
def test_media_adapter_executes_chrome_applescript(action: Action, output: str):
    calls = []

    def runner(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0, stdout=output, stderr="")

    executor = MacOSChromeMediaActionExecutor(
        system="Darwin", runner=runner, clock=ticking_clock(2.0, 2.025)
    )

    result = executor.execute(action)

    assert result.succeeded
    assert result.elapsed_ms == pytest.approx(25.0)
    assert calls[0][0][0][:2] == ["osascript", "-e"]
    script = calls[0][0][0][2]
    assert "set jsResult to execute javascript" in script
    assert "return jsResult" in script


def test_media_adapter_reports_missing_video_from_javascript_result():
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="no-video\n", stderr="")

    executor = MacOSChromeMediaActionExecutor(
        system="Darwin", runner=runner, clock=ticking_clock(2.0, 2.01)
    )

    result = executor.execute(Action.PAUSE_MEDIA)

    assert not result.succeeded
    assert result.error_reason == "media_not_found"


class FakeGpio:
    BCM = "BCM"
    OUT = "OUT"
    IN = "IN"
    LOW = 0
    HIGH = 1
    PUD_OFF = "PUD_OFF"

    def __init__(self) -> None:
        self.calls = []

    def setmode(self, mode):
        self.calls.append(("setmode", mode))

    def setup(self, pin, mode, **kwargs):
        self.calls.append(("setup", pin, mode, kwargs))

    def output(self, pin, value):
        self.calls.append(("output", pin, value))

    def cleanup(self, pins):
        self.calls.append(("cleanup", pins))


def test_gpio_adapter_controls_actions_and_restores_safe_state_on_close():
    gpio = FakeGpio()
    sleeps = []
    executor = RaspberryPiGpioActionExecutor(
        gpio=gpio,
        alert_pattern=(0.1, 0.2),
        sleeper=sleeps.append,
        clock=ticking_clock(1.0, 1.01, 2.0, 2.02, 3.0, 3.03),
    )

    assert executor.execute(Action.LIGHT_ON).succeeded
    assert executor.execute(Action.LIGHT_OFF).succeeded
    assert executor.execute(Action.BUZZER_ALERT).succeeded
    executor.close()
    executor.close()

    assert sleeps == [0.1, 0.2]
    assert ("output", 18, gpio.LOW) in gpio.calls
    assert gpio.calls.count(("cleanup", (17, 18))) == 1
    assert ("setup", 17, gpio.IN, {"pull_up_down": gpio.PUD_OFF}) in gpio.calls


def test_gpio_adapter_contains_action_and_safe_cleanup_failures():
    class FailingGpio(FakeGpio):
        def output(self, pin, value):
            super().output(pin, value)
            if pin == 17 or (pin == 18 and len(self.calls) > 3):
                raise RuntimeError("simulated GPIO failure")

    gpio = FailingGpio()
    executor = RaspberryPiGpioActionExecutor(
        gpio=gpio,
        clock=ticking_clock(1.0, 1.01),
    )

    result = executor.execute(Action.LIGHT_ON)

    assert not result.succeeded
    assert result.error_reason == "gpio_error_cleanup_failed"


def test_session_adapter_is_idempotent_and_records_duration():
    executor = SessionActionExecutor(clock=ticking_clock(10.0, 10.0, 12.0, 12.0, 15.5, 15.5))

    executor.execute(Action.START_SESSION)
    executor.execute(Action.START_SESSION)
    executor.execute(Action.END_SESSION)

    assert not executor.state.active
    assert executor.state.last_duration_seconds == pytest.approx(5.5)


@dataclass
class StubBackend:
    actions: list[Action]
    close_count: int = 0

    def execute(self, action: Action) -> ActionResult:
        self.actions.append(action)
        return ActionResult(action=action, succeeded=True)

    def close(self) -> None:
        self.close_count += 1


def test_composite_routes_all_actions_and_closes_shared_backends_once():
    media = StubBackend([])
    device = StubBackend([])
    session = StubBackend([])
    routes = {
        Action.PAUSE_MEDIA: media,
        Action.PLAY_MEDIA: media,
        Action.LIGHT_OFF: device,
        Action.LIGHT_ON: device,
        Action.BUZZER_ALERT: device,
        Action.START_SESSION: session,
        Action.END_SESSION: session,
    }

    with CompositeActionExecutor(routes) as executor:
        for action in Action:
            assert executor.execute(action).succeeded

    assert media.actions == [Action.PAUSE_MEDIA, Action.PLAY_MEDIA]
    assert device.actions == [Action.LIGHT_OFF, Action.LIGHT_ON, Action.BUZZER_ALERT]
    assert session.actions == [Action.START_SESSION, Action.END_SESSION]
    assert (media.close_count, device.close_count, session.close_count) == (1, 1, 1)


def test_composite_closes_remaining_backends_after_a_close_failure():
    class FailingBackend(StubBackend):
        def close(self) -> None:
            super().close()
            raise OSError("gpio cleanup failed")

    media = StubBackend([])
    device = FailingBackend([])
    session = StubBackend([])
    routes = {
        Action.PAUSE_MEDIA: media,
        Action.PLAY_MEDIA: media,
        Action.LIGHT_OFF: device,
        Action.LIGHT_ON: device,
        Action.BUZZER_ALERT: device,
        Action.START_SESSION: session,
        Action.END_SESSION: session,
    }

    with pytest.raises(OSError, match="gpio cleanup failed"):
        CompositeActionExecutor(routes).close()

    assert (media.close_count, device.close_count, session.close_count) == (1, 1, 1)


def test_composite_requires_a_route_for_every_action():
    with pytest.raises(ValueError, match="missing action routes"):
        CompositeActionExecutor({})


def _media_executor(returncode=0, stdout="", stderr=""):
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], returncode, stdout=stdout, stderr=stderr)

    return MacOSChromeMediaActionExecutor(
        system="Darwin", runner=runner, clock=ticking_clock(0.0, 0.01)
    )


def test_media_script_targets_the_matched_tab():
    # Without "in t" Chrome ignores the tab the loop found and returns "missing value".
    script = MacOSChromeMediaActionExecutor._script("pause")

    assert 'execute javascript "' in script
    assert '" in t' in script


def test_media_adapter_explains_the_chrome_javascript_setting():
    stderr = '"1+1" in t을(를) 가져올 수 없습니다. 접근이 허용되지 않습니다. (-1723)'

    result = _media_executor(returncode=1, stderr=stderr).execute(Action.PAUSE_MEDIA)

    assert result.error_reason == "javascript_not_allowed"
    assert "Apple Events에서 JavaScript 허용" in result.detail


def test_media_adapter_reports_other_applescript_errors_with_their_number():
    result = _media_executor(returncode=1, stderr="script error: 무엇인가 (-600)").execute(
        Action.PLAY_MEDIA
    )

    assert result.error_reason == "command_failed"
    assert result.detail == "Chrome AppleScript error -600"


def test_media_adapter_reports_a_failure_without_an_error_number():
    result = _media_executor(returncode=1, stderr="unknown failure").execute(Action.PLAY_MEDIA)

    assert (result.error_reason, result.detail) == ("command_failed", "Chrome media command failed")


def test_media_adapter_separates_missing_tab_from_missing_video():
    no_tab = _media_executor(stdout="no-youtube-tab\n").execute(Action.PAUSE_MEDIA)
    no_video = _media_executor(stdout="no-video\n").execute(Action.PAUSE_MEDIA)

    assert (no_tab.error_reason, no_tab.detail) == ("tab_not_found", "YouTube tab was not found")
    assert (no_video.error_reason, no_video.detail) == (
        "media_not_found",
        "YouTube video was not found",
    )


def test_media_adapter_flags_unexpected_output():
    result = _media_executor(stdout="missing value\n").execute(Action.PAUSE_MEDIA)

    assert (result.error_reason, result.detail) == (
        "unexpected_result",
        "unexpected Chrome response",
    )


def test_media_adapter_maps_script_errors_returned_through_stdout():
    result = _media_executor(stdout="applescript-error:-1723\n").execute(Action.PAUSE_MEDIA)

    assert result.error_reason == "javascript_not_allowed"
