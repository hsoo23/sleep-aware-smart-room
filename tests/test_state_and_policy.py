from sleep_aware.control.policy import Action, ClosedLoopPolicy, Intention
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
    assert policy.decide(Intention.SLEEP, DrowsinessState.AWAKE) == [Action.END_SESSION]


def test_wake_policy_resumes_media_after_recovery():
    policy = ClosedLoopPolicy()
    assert policy.decide(Intention.WAKE, DrowsinessState.DROWSY) == [
        Action.PAUSE_MEDIA,
        Action.LIGHT_ON,
        Action.BUZZER_ALERT,
    ]
    assert policy.decide(Intention.WAKE, DrowsinessState.AWAKE) == [Action.PLAY_MEDIA]
