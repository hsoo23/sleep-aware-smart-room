import numpy as np
import pytest

from sleep_aware.detection.ear import calculate_ear, calculate_eye_ears
from sleep_aware.pipeline import EyeLandmarks, Point


def test_calculate_ear_known_geometry():
    points = np.array([[0, 0], [1, 1], [3, 1], [4, 0], [3, -1], [1, -1]])
    assert calculate_ear(points) == pytest.approx(0.5)


def test_calculate_ear_rejects_invalid_shape():
    with pytest.raises(ValueError):
        calculate_ear(np.zeros((5, 2)))


def test_calculate_eye_ears_returns_both_eyes_and_mean():
    def eye(vertical):
        coordinates = ((0, 0), (1, vertical), (3, vertical), (4, 0), (3, -vertical), (1, -vertical))
        return tuple(Point(x, y) for x, y in coordinates)

    left, right, mean = calculate_eye_ears(EyeLandmarks(eye(1.0), eye(0.5)))

    assert left == pytest.approx(0.5)
    assert right == pytest.approx(0.25)
    assert mean == pytest.approx(0.375)
