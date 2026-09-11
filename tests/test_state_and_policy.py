from sleep_aware.control.policy import Action, ClosedLoopPolicy, Intention
from sleep_aware.detection.state import DrowsinessState, TemporalDrowsinessDetector


def test_temporal_detector_is_time_based():
    detector = TemporalDrowsinessDetector(ear_threshold=0.21, drowsy_seconds=2.0)
    assert detector.update(0.0, 0.18) is DrowsinessState.EYES_CLOSED
    assert detector.update(1.9, 0.18) is DrowsinessState.EYES_CLOSED
    assert detector.update(2.0, 0.18) is DrowsinessState.DROWSY


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
