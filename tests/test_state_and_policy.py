from sleep_aware.control.policy import (
    Action,
    ClosedLoopPolicy,
    Intention,
    PolicyPhase,
    TransitionReason,
)
from sleep_aware.detection.state import DrowsinessState, TemporalDrowsinessDetector


def test_temporal_detector_is_time_based():
    detector = TemporalDrowsinessDetector(ear_threshold=0.21, drowsy_seconds=2.0)
    assert detector.update(0.0, 0.18) is DrowsinessState.EYES_CLOSED
    assert detector.update(1.9, 0.18) is DrowsinessState.EYES_CLOSED
    assert detector.update(2.0, 0.18) is DrowsinessState.DROWSY


def test_first_open_eye_observation_is_immediately_awake():
    detector = TemporalDrowsinessDetector(recovery_seconds=0.5)

    assert detector.update(10.0, 0.3) is DrowsinessState.AWAKE


def test_recovery_delay_still_applies_after_closed_eyes():
    detector = TemporalDrowsinessDetector(recovery_seconds=0.5)
    assert detector.update(0.0, 0.1) is DrowsinessState.EYES_CLOSED
    assert detector.update(1.0, 0.3) is DrowsinessState.EYES_CLOSED
    assert detector.update(1.5, 0.3) is DrowsinessState.AWAKE


def test_recovery_delay_applies_after_face_is_temporarily_lost():
    detector = TemporalDrowsinessDetector(recovery_seconds=0.5)
    assert detector.update(0.0, 0.1) is DrowsinessState.EYES_CLOSED
    assert detector.update(1.0, None) is DrowsinessState.NO_FACE
    assert detector.update(1.1, 0.3) is DrowsinessState.NO_FACE
    assert detector.update(1.5, 0.3) is DrowsinessState.NO_FACE
    assert detector.update(1.6, 0.3) is DrowsinessState.AWAKE


def test_closed_eyes_after_face_loss_restart_drowsy_timer():
    detector = TemporalDrowsinessDetector(drowsy_seconds=2.0)
    assert detector.update(0.0, 0.1) is DrowsinessState.EYES_CLOSED
    assert detector.update(2.0, 0.1) is DrowsinessState.DROWSY
    assert detector.update(2.1, None) is DrowsinessState.NO_FACE
    assert detector.update(4.0, 0.1) is DrowsinessState.EYES_CLOSED
    assert detector.update(6.0, 0.1) is DrowsinessState.DROWSY


def test_sleep_policy_closes_loop_on_recovery():
    policy = ClosedLoopPolicy()
    assert policy.decide(Intention.SLEEP, DrowsinessState.DROWSY) == [
        Action.PAUSE_MEDIA,
        Action.LIGHT_OFF,
        Action.START_SESSION,
    ]
    assert policy.decide(Intention.SLEEP, DrowsinessState.DROWSY) == []
    assert policy.decide(Intention.SLEEP, DrowsinessState.EYES_CLOSED) == []
    assert policy.decide(Intention.SLEEP, DrowsinessState.NO_FACE) == []
    assert policy.phase is PolicyPhase.AWAITING_RECOVERY
    assert policy.decide(Intention.SLEEP, DrowsinessState.AWAKE) == [Action.END_SESSION]
    assert policy.phase is PolicyPhase.IDLE


def test_wake_policy_resumes_media_after_recovery():
    policy = ClosedLoopPolicy()
    assert policy.decide(Intention.WAKE, DrowsinessState.DROWSY) == [
        Action.PAUSE_MEDIA,
        Action.LIGHT_ON,
        Action.BUZZER_ALERT,
    ]
    assert policy.decide(Intention.WAKE, DrowsinessState.NO_FACE) == []
    assert policy.decide(Intention.WAKE, DrowsinessState.EYES_CLOSED) == []
    assert policy.decide(Intention.WAKE, DrowsinessState.AWAKE) == [Action.PLAY_MEDIA]


def test_recovered_episode_allows_one_new_drowsy_action_sequence():
    policy = ClosedLoopPolicy()

    first_actions = policy.decide(Intention.WAKE, DrowsinessState.DROWSY)
    assert policy.decide(Intention.WAKE, DrowsinessState.DROWSY) == []
    assert policy.decide(Intention.WAKE, DrowsinessState.AWAKE) == [Action.PLAY_MEDIA]

    assert policy.decide(Intention.WAKE, DrowsinessState.DROWSY) == first_actions


def test_mode_change_discards_previous_mode_episode_state():
    policy = ClosedLoopPolicy()
    policy.decide(Intention.SLEEP, DrowsinessState.DROWSY)

    transition = policy.transition(Intention.WAKE, DrowsinessState.AWAKE)

    assert transition.reason is TransitionReason.INTENTION_CHANGED
    assert transition.previous_phase is PolicyPhase.AWAITING_RECOVERY
    assert transition.next_phase is PolicyPhase.IDLE
    assert transition.actions == (Action.END_SESSION, Action.PLAY_MEDIA)
    assert policy.decide(Intention.WAKE, DrowsinessState.DROWSY) == [
        Action.PAUSE_MEDIA,
        Action.LIGHT_ON,
        Action.BUZZER_ALERT,
    ]


def test_reset_discards_episode_and_session_ownership():
    policy = ClosedLoopPolicy()
    policy.decide(Intention.SLEEP, DrowsinessState.DROWSY)

    policy.reset(Intention.SLEEP)

    assert policy.phase is PolicyPhase.AWAITING_RECOVERY
    transition = policy.transition(Intention.SLEEP, DrowsinessState.AWAKE)
    assert transition.reason is TransitionReason.RESET
    assert transition.actions == (Action.END_SESSION, Action.PLAY_MEDIA)
    assert policy.phase is PolicyPhase.IDLE


def test_reset_resumes_media_paused_by_wake_episode():
    policy = ClosedLoopPolicy()
    policy.decide(Intention.WAKE, DrowsinessState.DROWSY)

    policy.reset(Intention.WAKE)
    transition = policy.transition(Intention.WAKE, DrowsinessState.AWAKE)

    assert transition.reason is TransitionReason.RESET
    assert transition.actions == (Action.PLAY_MEDIA,)
    assert policy.phase is PolicyPhase.IDLE


def test_transition_explains_actions_with_previous_and_next_phase():
    policy = ClosedLoopPolicy()

    transition = policy.transition(Intention.WAKE, DrowsinessState.DROWSY)

    assert transition.reason is TransitionReason.DROWSY_DETECTED
    assert transition.previous_phase is PolicyPhase.IDLE
    assert transition.next_phase is PolicyPhase.AWAITING_RECOVERY
    assert transition.actions == (
        Action.PAUSE_MEDIA,
        Action.LIGHT_ON,
        Action.BUZZER_ALERT,
    )
