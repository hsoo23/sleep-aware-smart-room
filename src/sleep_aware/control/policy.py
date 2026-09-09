"""Pure decision logic for intention-aware smart-room control.

The policy emits actions only when a state transition requires them. Device
drivers and HTTP/GPIO adapters remain outside this module so the policy can
be tested without a camera, Raspberry Pi, or media player.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sleep_aware.detection.state import DrowsinessState


class Intention(str, Enum):
    SLEEP = "sleep"
    WAKE = "wake"


class Action(str, Enum):
    PAUSE_MEDIA = "pause_media"
    PLAY_MEDIA = "play_media"
    LIGHT_OFF = "light_off"
    LIGHT_ON = "light_on"
    BUZZER_ALERT = "buzzer_alert"
    START_SESSION = "start_session"
    END_SESSION = "end_session"


@dataclass
class ClosedLoopPolicy:
    """Translate detected states into idempotent mode-specific actions."""

    _drowsy_action_sent: bool = False
    _sleep_session_active: bool = False
    _media_paused_by_system: bool = False

    def decide(
        self, intention: Intention, state: DrowsinessState
    ) -> list[Action]:
        if state is DrowsinessState.DROWSY:
            return self._on_drowsy(intention)
        if state is DrowsinessState.AWAKE:
            return self._on_awake(intention)
        return []

    def _on_drowsy(self, intention: Intention) -> list[Action]:
        if self._drowsy_action_sent:
            return []

        self._drowsy_action_sent = True
        self._media_paused_by_system = True
        if intention is Intention.SLEEP:
            self._sleep_session_active = True
            return [Action.PAUSE_MEDIA, Action.LIGHT_OFF, Action.START_SESSION]
        if intention is Intention.WAKE:
            return [Action.PAUSE_MEDIA, Action.LIGHT_ON, Action.BUZZER_ALERT]
        raise ValueError(f"unsupported intention: {intention}")

    def _on_awake(self, intention: Intention) -> list[Action]:
        actions: list[Action] = []
        if intention is Intention.WAKE and self._media_paused_by_system:
            actions.append(Action.PLAY_MEDIA)
            self._media_paused_by_system = False
        elif intention is Intention.SLEEP and self._sleep_session_active:
            actions.append(Action.END_SESSION)
            self._sleep_session_active = False

        self._drowsy_action_sent = False
        return actions
