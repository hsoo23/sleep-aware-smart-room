"""Platform-specific action adapters and safe action routing."""

from __future__ import annotations

import platform
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from sleep_aware.control import Action
from sleep_aware.pipeline.models import ActionResult


class ActionBackend(Protocol):
    """Small contract implemented by one platform-specific action backend."""

    def execute(self, action: Action) -> ActionResult: ...

    def close(self) -> None: ...


def _elapsed_ms(clock: Callable[[], float], started_at: float) -> float:
    return max(0.0, (clock() - started_at) * 1000.0)


class MacOSChromeMediaActionExecutor:
    """Pause or resume the first YouTube video found in Google Chrome."""

    SUPPORTED_ACTIONS = frozenset({Action.PAUSE_MEDIA, Action.PLAY_MEDIA})

    def __init__(
        self,
        *,
        system: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._system = system or platform.system()
        self._runner = runner
        self._clock = clock

    def execute(self, action: Action) -> ActionResult:
        started_at = self._clock()
        if action not in self.SUPPORTED_ACTIONS:
            return self._failure(action, started_at, "unsupported_action")
        if self._system != "Darwin":
            return self._failure(action, started_at, "unsupported_platform")

        command = "pause" if action is Action.PAUSE_MEDIA else "play"
        script = self._script(command)
        try:
            completed = self._runner(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return self._failure(action, started_at, "process_error")

        elapsed = _elapsed_ms(self._clock, started_at)
        if completed.returncode != 0:
            return ActionResult(
                action=action,
                succeeded=False,
                detail="Chrome media command failed",
                elapsed_ms=elapsed,
                error_reason="command_failed",
            )
        result = completed.stdout.strip()
        if result != command:
            return ActionResult(
                action=action,
                succeeded=False,
                detail="YouTube video was not found",
                elapsed_ms=elapsed,
                error_reason="media_not_found",
            )
        return ActionResult(action=action, succeeded=True, detail=result, elapsed_ms=elapsed)

    def close(self) -> None:
        """The AppleScript adapter owns no persistent resource."""

    def _failure(self, action: Action, started_at: float, reason: str) -> ActionResult:
        return ActionResult(
            action=action,
            succeeded=False,
            detail=reason.replace("_", " "),
            elapsed_ms=_elapsed_ms(self._clock, started_at),
            error_reason=reason,
        )

    @staticmethod
    def _script(command: str) -> str:
        return f'''
tell application "Google Chrome"
    repeat with w in windows
        repeat with t in tabs of w
            if URL of t contains "youtube.com" then
                set jsResult to execute javascript "var v=document.querySelector('video'); if(v){{v.{command}();'{command}'}}else{{'no video'}}"
                return jsResult
            end if
        end repeat
    end repeat
    return "no video"
end tell
'''


class RaspberryPiGpioActionExecutor:
    """Control an active-low relay and buzzer while guaranteeing safe cleanup."""

    SUPPORTED_ACTIONS = frozenset(
        {Action.LIGHT_ON, Action.LIGHT_OFF, Action.BUZZER_ALERT}
    )

    def __init__(
        self,
        *,
        gpio: Any,
        relay_pin: int = 17,
        buzzer_pin: int = 18,
        alert_pattern: Sequence[float] = (0.25,) * 10,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if relay_pin == buzzer_pin:
            raise ValueError("relay_pin and buzzer_pin must differ")
        if any(duration < 0 for duration in alert_pattern):
            raise ValueError("alert_pattern durations must be non-negative")
        self._gpio = gpio
        self._relay_pin = relay_pin
        self._buzzer_pin = buzzer_pin
        self._alert_pattern = tuple(alert_pattern)
        self._sleeper = sleeper
        self._clock = clock
        self._closed = False
        gpio.setmode(gpio.BCM)
        gpio.setup(buzzer_pin, gpio.OUT)
        gpio.output(buzzer_pin, gpio.LOW)

    def execute(self, action: Action) -> ActionResult:
        started_at = self._clock()
        if self._closed:
            return self._failure(action, started_at, "executor_closed")
        if action not in self.SUPPORTED_ACTIONS:
            return self._failure(action, started_at, "unsupported_action")
        try:
            if action is Action.LIGHT_ON:
                self._gpio.setup(self._relay_pin, self._gpio.OUT)
                self._gpio.output(self._relay_pin, self._gpio.LOW)
            elif action is Action.LIGHT_OFF:
                self._gpio.setup(
                    self._relay_pin,
                    self._gpio.IN,
                    pull_up_down=self._gpio.PUD_OFF,
                )
            else:
                for index, duration in enumerate(self._alert_pattern):
                    level = self._gpio.HIGH if index % 2 == 0 else self._gpio.LOW
                    self._gpio.output(self._buzzer_pin, level)
                    self._sleeper(duration)
                self._gpio.output(self._buzzer_pin, self._gpio.LOW)
        except (OSError, RuntimeError, ValueError):
            try:
                self._safe_outputs()
            except (OSError, RuntimeError, ValueError):
                return self._failure(action, started_at, "gpio_error_cleanup_failed")
            return self._failure(action, started_at, "gpio_error")
        return ActionResult(
            action=action,
            succeeded=True,
            elapsed_ms=_elapsed_ms(self._clock, started_at),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._safe_outputs()
        self._gpio.cleanup((self._relay_pin, self._buzzer_pin))
        self._closed = True

    def _safe_outputs(self) -> None:
        self._gpio.output(self._buzzer_pin, self._gpio.LOW)
        self._gpio.setup(
            self._relay_pin,
            self._gpio.IN,
            pull_up_down=self._gpio.PUD_OFF,
        )

    def _failure(self, action: Action, started_at: float, reason: str) -> ActionResult:
        return ActionResult(
            action=action,
            succeeded=False,
            detail=reason.replace("_", " "),
            elapsed_ms=_elapsed_ms(self._clock, started_at),
            error_reason=reason,
        )


@dataclass(frozen=True)
class SessionState:
    active: bool = False
    started_at: float | None = None
    last_duration_seconds: float | None = None


class SessionActionExecutor:
    """Track sleep-session start/end without coupling policy to reporting."""

    SUPPORTED_ACTIONS = frozenset({Action.START_SESSION, Action.END_SESSION})

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._state = SessionState()

    @property
    def state(self) -> SessionState:
        return self._state

    def execute(self, action: Action) -> ActionResult:
        started_at = self._clock()
        if action not in self.SUPPORTED_ACTIONS:
            return ActionResult(action, False, "unsupported action", 0.0, "unsupported_action")
        if action is Action.START_SESSION:
            if not self._state.active:
                self._state = SessionState(active=True, started_at=started_at)
        elif self._state.active and self._state.started_at is not None:
            duration = max(0.0, started_at - self._state.started_at)
            self._state = SessionState(last_duration_seconds=duration)
        return ActionResult(
            action=action,
            succeeded=True,
            elapsed_ms=_elapsed_ms(self._clock, started_at),
        )

    def close(self) -> None:
        self._state = SessionState(last_duration_seconds=self._state.last_duration_seconds)


class CompositeActionExecutor:
    """Route every action to one owner and close all owners safely."""

    def __init__(self, routes: Mapping[Action, ActionBackend]) -> None:
        missing = set(Action) - set(routes)
        if missing:
            names = ", ".join(sorted(action.value for action in missing))
            raise ValueError(f"missing action routes: {names}")
        self._routes = dict(routes)

    def execute(self, action: Action) -> ActionResult:
        return self._routes[action].execute(action)

    def close(self) -> None:
        """Close every distinct backend, then re-raise the first close failure."""
        seen: set[int] = set()
        first_error: Exception | None = None
        for backend in reversed(tuple(self._routes.values())):
            identity = id(backend)
            if identity in seen:
                continue
            seen.add(identity)
            try:
                backend.close()
            except Exception as error:  # noqa: BLE001 - later backends must still be released.
                if first_error is None:
                    first_error = error
        if first_error is not None:
            raise first_error

    def __enter__(self) -> CompositeActionExecutor:  # noqa: PYI034
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
