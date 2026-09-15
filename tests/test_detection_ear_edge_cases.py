import numpy as np
import pytest

from sleep_aware.detection.ear import calculate_ear

OPEN_EYE = [[0, 0], [1, 1], [3, 1], [4, 0], [3, -1], [1, -1]]


def test_ear_is_invariant_to_translation_and_uniform_scale():
    points = np.array(OPEN_EYE, dtype=float)
    transformed = points * 37.5 + np.array([120.0, -48.0])

    assert calculate_ear(transformed) == pytest.approx(calculate_ear(points))


def test_ear_accepts_nested_sequence_input():
    assert calculate_ear(OPEN_EYE) == pytest.approx(0.5)


def test_ear_is_zero_for_fully_closed_eye():
    closed = [[0, 0], [1, 0], [3, 0], [4, 0], [3, 0], [1, 0]]

    assert calculate_ear(closed) == pytest.approx(0.0)


def test_ear_rejects_zero_horizontal_eye_width():
    degenerate = [[0, 0], [0, 1], [0, 1], [0, 0], [0, -1], [0, -1]]

    with pytest.raises(ValueError, match="horizontal"):
        calculate_ear(degenerate)


@pytest.mark.parametrize("shape", [(6, 3), (12,), (2, 6), (7, 2)])
def test_ear_rejects_landmarks_that_are_not_six_2d_points(shape):
    with pytest.raises(ValueError, match="shape"):
        calculate_ear(np.zeros(shape))
