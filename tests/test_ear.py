import numpy as np
import pytest

from sleep_aware.detection.ear import calculate_ear


def test_calculate_ear_known_geometry():
    points = np.array([[0, 0], [1, 1], [3, 1], [4, 0], [3, -1], [1, -1]])
    assert calculate_ear(points) == pytest.approx(0.5)


def test_calculate_ear_rejects_invalid_shape():
    with pytest.raises(ValueError):
        calculate_ear(np.zeros((5, 2)))

