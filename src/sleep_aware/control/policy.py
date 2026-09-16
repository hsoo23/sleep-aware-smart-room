"""Pure decision logic for intention-aware smart-room control.

The policy emits actions only when a state transition requires them. Device
drivers and HTTP/GPIO adapters remain outside this module so the policy can
be tested without a camera, Raspberry Pi, or media player.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


class PolicyPhase(str, Enum):
    """Mode-local phase of one drowsiness episode."""

    IDLE = "idle"
    AWAITING_RECOVERY = "awaiting_recovery"


class TransitionReason(str, Enum):
    """Why a policy observation did or did not produce a transition."""

    NO_TRANSITION = "no_transition"
    DROWSY_DETECTED = "drowsy_detected"
    DUPLICATE_DROWSY = "duplicate_drowsy"
    WAITING_FOR_RECOVERY = "waiting_for_recovery"
    NO_FACE_IGNORED = "no_face_ignored"
    RECOVERY_CONFIRMED = "recovery_confirmed"
    INTENTION_CHANGED = "intention_changed"
    RESET = "reset"


@dataclass(frozen=True)
class PolicyTransition:
    """A loggable explanation of a decision for one observation."""

    intention: Intention
    observed_state: DrowsinessState
    previous_phase: PolicyPhase
    next_phase: PolicyPhase
    reason: TransitionReason
    actions: tuple[Action, ...] = ()


@dataclass
class ClosedLoopPolicy:
    """Translate observations into idempotent, mode-specific transitions."""

    _intention: Intention | None = field(default=None, init=False)
    _phase: PolicyPhase = field(default=PolicyPhase.IDLE, init=False)
    _sleep_session_active: bool = field(default=False, init=False)
    _media_paused_by_system: bool = field(default=False, init=False)
    _pending_intention: Intention | None = field(default=None, init=False)
    _pending_reset_reason: TransitionReason | None = field(default=None, init=False)

    @property
    def phase(self) -> PolicyPhase:
        return self._phase

    def reset(self, intention: Intention | None = None) -> None:
        """Request a clean lifecycle boundary without losing owned resources."""
        if self._sleep_session_active or self._media_paused_by_system:
            self._pending_intention = intention
            self._pending_reset_reason = TransitionReason.RESET
            return
        self._clear(intention)

    def _clear(self, intention: Intention | None) -> None:
        """Clear internal state after no cleanup is needed or cleanup is emitted."""
        self._intention = intention
        self._phase = PolicyPhase.IDLE
        self._sleep_session_active = False
        self._media_paused_by_system = False
        self._pending_intention = None
        self._pending_reset_reason = None

    def decide(self, intention: Intention, state: DrowsinessState) -> list[Action]:
        """Return actions for callers that do not need transition metadata."""
        return list(self.transition(intention, state).actions)

    def transition(
        self, intention: Intention, state: DrowsinessState
    ) -> PolicyTransition:
        """Observe a state and return the complete policy transition record."""
        if not isinstance(intention, Intention):
            raise TypeError(f"unsupported intention: {intention}")

        if self._pending_reset_reason is not None:
            return self._complete_reset(intention, state)

        previous_phase = self._phase
        intention_changed = self._intention is not None and intention is not self._intention
        if intention_changed:
            if self._sleep_session_active or self._media_paused_by_system:
                self._pending_intention = intention
                self._pending_reset_reason = TransitionReason.INTENTION_CHANGED
                return self._complete_reset(intention, state)
            self._clear(intention)
        elif self._intention is None:
            self._intention = intention

        if state is DrowsinessState.DROWSY:
            transition = self._on_drowsy(intention, previous_phase)
        elif state is DrowsinessState.AWAKE:
            transition = self._on_awake(intention, previous_phase)
        elif state is DrowsinessState.NO_FACE:
            transition = self._unchanged(
                intention,
                state,
                previous_phase,
                TransitionReason.NO_FACE_IGNORED,
            )
        elif state is DrowsinessState.EYES_CLOSED:
            transition = self._unchanged(
                intention,
                state,
                previous_phase,
                TransitionReason.WAITING_FOR_RECOVERY,
            )
        else:
            raise ValueError(f"unsupported drowsiness state: {state}")

        if intention_changed and not transition.actions:
            return PolicyTransition(
                intention=intention,
                observed_state=state,
                previous_phase=previous_phase,
                next_phase=self._phase,
                reason=TransitionReason.INTENTION_CHANGED,
            )
        return transition

    def _complete_reset(
        self, intention: Intention, state: DrowsinessState
    ) -> PolicyTransition:
        """Emit cleanup actions before completing a reset or mode change."""
        previous_phase = self._phase
        next_intention = self._pending_intention or intention
        reason = self._pending_reset_reason
        if next_intention is None or reason is None:
            raise RuntimeError("reset cleanup requested without lifecycle metadata")

        actions: list[Action] = []
        if self._sleep_session_active:
            actions.append(Action.END_SESSION)
        if self._media_paused_by_system:
            actions.append(Action.PLAY_MEDIA)

        self._clear(next_intention)
        return PolicyTransition(
            intention=next_intention,
            observed_state=state,
            previous_phase=previous_phase,
            next_phase=self._phase,
            reason=reason,
            actions=tuple(actions),
        )

    def _on_drowsy(
        self, intention: Intention, previous_phase: PolicyPhase
    ) -> PolicyTransition:
        if self._phase is PolicyPhase.AWAITING_RECOVERY:
            return self._unchanged(
                intention,
                DrowsinessState.DROWSY,
                previous_phase,
                TransitionReason.DUPLICATE_DROWSY,
            )

        self._phase = PolicyPhase.AWAITING_RECOVERY
        self._media_paused_by_system = True
        if intention is Intention.SLEEP:
            self._sleep_session_active = True
            actions = (Action.PAUSE_MEDIA, Action.LIGHT_OFF, Action.START_SESSION)
        else:
            actions = (Action.PAUSE_MEDIA, Action.LIGHT_ON, Action.BUZZER_ALERT)
        return PolicyTransition(
            intention=intention,
            observed_state=DrowsinessState.DROWSY,
            previous_phase=previous_phase,
            next_phase=self._phase,
            reason=TransitionReason.DROWSY_DETECTED,
            actions=actions,
        )

    def _on_awake(
        self, intention: Intention, previous_phase: PolicyPhase
    ) -> PolicyTransition:
        if self._phase is PolicyPhase.IDLE:
            return self._unchanged(
                intention,
                DrowsinessState.AWAKE,
                previous_phase,
                TransitionReason.NO_TRANSITION,
            )

        if intention is Intention.WAKE and self._media_paused_by_system:
            actions = (Action.PLAY_MEDIA,)
        elif intention is Intention.SLEEP and self._sleep_session_active:
            actions = (Action.END_SESSION,)
        else:
            actions = ()

        self._phase = PolicyPhase.IDLE
        self._sleep_session_active = False
        self._media_paused_by_system = False
        return PolicyTransition(
            intention=intention,
            observed_state=DrowsinessState.AWAKE,
            previous_phase=previous_phase,
            next_phase=self._phase,
            reason=TransitionReason.RECOVERY_CONFIRMED,
            actions=actions,
        )

    def _unchanged(
        self,
        intention: Intention,
        state: DrowsinessState,
        previous_phase: PolicyPhase,
        reason: TransitionReason,
    ) -> PolicyTransition:
        return PolicyTransition(
            intention=intention,
            observed_state=state,
            previous_phase=previous_phase,
            next_phase=self._phase,
            reason=reason,
        )
