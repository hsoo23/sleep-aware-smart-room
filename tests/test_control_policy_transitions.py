import pytest

from sleep_aware.control.policy import Action, ClosedLoopPolicy, Intention
from sleep_aware.detection.state import DrowsinessState

DROWSY_ACTIONS = {
    Intention.SLEEP: [Action.PAUSE_MEDIA, Action.LIGHT_OFF, Action.START_SESSION],
    Intention.WAKE: [Action.PAUSE_MEDIA, Action.LIGHT_ON, Action.BUZZER_ALERT],
}
RECOVERY_ACTIONS = {
    Intention.SLEEP: [Action.END_SESSION],
    Intention.WAKE: [Action.PLAY_MEDIA],
}


@pytest.mark.parametrize("intention", list(Intention))
def test_policy_awake_before_any_drowsy_emits_nothing(intention):
    policy = ClosedLoopPolicy()

    assert policy.decide(intention, DrowsinessState.AWAKE) == []


@pytest.mark.parametrize("intention", list(Intention))
@pytest.mark.parametrize("state", [DrowsinessState.NO_FACE, DrowsinessState.EYES_CLOSED])
def test_policy_non_decisive_states_emit_nothing_when_idle(intention, state):
    policy = ClosedLoopPolicy()

    assert policy.decide(intention, state) == []


@pytest.mark.parametrize("intention", list(Intention))
def test_policy_no_face_and_eyes_closed_do_not_rearm_drowsy_actions(intention):
    policy = ClosedLoopPolicy()
    assert policy.decide(intention, DrowsinessState.DROWSY) == DROWSY_ACTIONS[intention]

    assert policy.decide(intention, DrowsinessState.NO_FACE) == []
    assert policy.decide(intention, DrowsinessState.EYES_CLOSED) == []
    assert policy.decide(intention, DrowsinessState.DROWSY) == []
    assert policy.decide(intention, DrowsinessState.AWAKE) == RECOVERY_ACTIONS[intention]


@pytest.mark.parametrize("intention", list(Intention))
def test_policy_rearms_drowsy_actions_after_recovery(intention):
    policy = ClosedLoopPolicy()

    for _ in range(2):
        assert policy.decide(intention, DrowsinessState.DROWSY) == DROWSY_ACTIONS[intention]
        assert policy.decide(intention, DrowsinessState.AWAKE) == RECOVERY_ACTIONS[intention]


@pytest.mark.parametrize("intention", list(Intention))
def test_policy_repeated_awake_after_recovery_emits_nothing(intention):
    policy = ClosedLoopPolicy()
    policy.decide(intention, DrowsinessState.DROWSY)
    policy.decide(intention, DrowsinessState.AWAKE)

    assert policy.decide(intention, DrowsinessState.AWAKE) == []


def test_policy_sleep_mode_never_sounds_buzzer_or_turns_light_on():
    policy = ClosedLoopPolicy()
    emitted = [
        action
        for state in (DrowsinessState.DROWSY, DrowsinessState.AWAKE) * 2
        for action in policy.decide(Intention.SLEEP, state)
    ]

    assert Action.BUZZER_ALERT not in emitted
    assert Action.LIGHT_ON not in emitted


def test_policy_wake_mode_never_turns_light_off_or_starts_sleep_session():
    policy = ClosedLoopPolicy()
    emitted = [
        action
        for state in (DrowsinessState.DROWSY, DrowsinessState.AWAKE) * 2
        for action in policy.decide(Intention.WAKE, state)
    ]

    assert Action.LIGHT_OFF not in emitted
    assert Action.START_SESSION not in emitted
    assert Action.END_SESSION not in emitted


def test_policy_rejects_unsupported_intention_on_drowsy():
    policy = ClosedLoopPolicy()

    with pytest.raises(ValueError, match="unsupported intention"):
        policy.decide("nap", DrowsinessState.DROWSY)
