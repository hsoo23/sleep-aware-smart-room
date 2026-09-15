import math

import pytest

from sleep_aware.detection.state import DrowsinessState, TemporalDrowsinessDetector

OPEN = 0.30
CLOSED = 0.10


def _detector() -> TemporalDrowsinessDetector:
    return TemporalDrowsinessDetector(ear_threshold=0.21, drowsy_seconds=2.0, recovery_seconds=0.5)


def _drowsy_detector() -> TemporalDrowsinessDetector:
    detector = _detector()
    detector.update(0.0, CLOSED)
    assert detector.update(2.0, CLOSED) is DrowsinessState.DROWSY
    return detector


def test_temporal_state_missing_ear_is_no_face():
    detector = _detector()

    assert detector.update(0.0, None) is DrowsinessState.NO_FACE


def test_temporal_state_ear_equal_to_threshold_counts_as_open():
    detector = _detector()
    detector.update(0.0, CLOSED)
    detector.update(1.0, 0.21)

    # The closed-eye timer restarted at 2.5, so 1.9 s later it is not yet DROWSY.
    assert detector.update(2.5, CLOSED) is DrowsinessState.EYES_CLOSED
    assert detector.update(4.4, CLOSED) is DrowsinessState.EYES_CLOSED
    assert detector.update(4.5, CLOSED) is DrowsinessState.DROWSY


def test_temporal_state_short_open_frame_restarts_closed_timer():
    detector = _detector()
    detector.update(0.0, CLOSED)
    detector.update(1.5, CLOSED)
    detector.update(1.6, OPEN)

    assert detector.update(1.7, CLOSED) is DrowsinessState.EYES_CLOSED
    assert detector.update(3.6, CLOSED) is DrowsinessState.EYES_CLOSED
    assert detector.update(3.7, CLOSED) is DrowsinessState.DROWSY


def test_temporal_state_no_face_restarts_closed_timer():
    detector = _detector()
    detector.update(0.0, CLOSED)
    assert detector.update(1.5, None) is DrowsinessState.NO_FACE

    assert detector.update(1.6, CLOSED) is DrowsinessState.EYES_CLOSED
    assert detector.update(3.5, CLOSED) is DrowsinessState.EYES_CLOSED
    assert detector.update(3.6, CLOSED) is DrowsinessState.DROWSY


def test_temporal_state_drowsy_holds_until_recovery_duration_elapses():
    detector = _drowsy_detector()

    assert detector.update(2.1, OPEN) is DrowsinessState.DROWSY
    assert detector.update(2.5, OPEN) is DrowsinessState.DROWSY
    assert detector.update(2.6, OPEN) is DrowsinessState.AWAKE


def test_temporal_state_closure_during_recovery_restarts_recovery_timer():
    detector = _drowsy_detector()
    detector.update(2.1, OPEN)
    detector.update(2.4, CLOSED)

    # Recovery needs recovery_seconds of continuous open eyes after the last closure.
    assert detector.update(2.5, OPEN) is not DrowsinessState.AWAKE
    assert detector.update(2.9, OPEN) is not DrowsinessState.AWAKE
    assert detector.update(3.0, OPEN) is DrowsinessState.AWAKE


@pytest.mark.parametrize("fps", [5, 15, 30, 60])
def test_temporal_state_drowsy_onset_is_independent_of_frame_rate(fps):
    detector = _detector()
    states = [detector.update(index / fps, CLOSED) for index in range(3 * fps)]

    first_drowsy = states.index(DrowsinessState.DROWSY)
    assert first_drowsy / fps == pytest.approx(2.0)
    assert first_drowsy == math.ceil(2.0 * fps)
    assert set(states[:first_drowsy]) == {DrowsinessState.EYES_CLOSED}
