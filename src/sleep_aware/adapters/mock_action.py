"""In-memory action executor for repeatable closed-loop tests."""

from __future__ import annotations

from dataclasses import dataclass

from sleep_aware.control import Action
from sleep_aware.pipeline.models import ActionResult


@dataclass(frozen=True)
class DeviceState:
    """Observable state of the devices represented by the mock."""

    light_on: bool = True
    buzzer_alert_count: int = 0
    media_playing: bool = True
    session_active: bool = False


class MockActionExecutor:
    """Apply actions to memory without network or physical hardware access."""

    def __init__(self, initial_state: DeviceState | None = None) -> None:
        state = initial_state or DeviceState()
        self._light_on = state.light_on
        self._buzzer_alert_count = state.buzzer_alert_count
        self._media_playing = state.media_playing
        self._session_active = state.session_active
        self.history: list[Action] = []

    @property
    def state(self) -> DeviceState:
        """Return an immutable snapshot of the current mock state."""
        return DeviceState(
            light_on=self._light_on,
            buzzer_alert_count=self._buzzer_alert_count,
            media_playing=self._media_playing,
            session_active=self._session_active,
        )

    def execute(self, action: Action) -> ActionResult:
        """Apply one action; repeated state-setting commands remain safe."""
        self.history.append(action)
        if action is Action.PAUSE_MEDIA:
            self._media_playing = False
        elif action is Action.PLAY_MEDIA:
            self._media_playing = True
        elif action is Action.LIGHT_OFF:
            self._light_on = False
        elif action is Action.LIGHT_ON:
            self._light_on = True
        elif action is Action.BUZZER_ALERT:
            self._buzzer_alert_count += 1
        elif action is Action.START_SESSION:
            self._session_active = True
        elif action is Action.END_SESSION:
            self._session_active = False
        else:  # pragma: no cover - protects runtime callers bypassing the enum type.
            return ActionResult(
                action=action,
                succeeded=False,
                detail="unsupported action",
                elapsed_ms=0.0,
                error_reason="unsupported_action",
            )
        return ActionResult(action=action, succeeded=True, elapsed_ms=0.0)
