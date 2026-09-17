"""Eye Aspect Ratio feature calculation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sleep_aware.pipeline.models import EyeLandmarks, Point


def _eye_array(
    points: tuple[Point, Point, Point, Point, Point, Point],
) -> np.ndarray:
    return np.asarray([(point.x, point.y) for point in points], dtype=float)


def calculate_ear(eye_points: np.ndarray) -> float:
    """Return EAR for six ordered 2-D eye landmarks.

    Landmark order follows p1..p6 in the standard EAR equation.
    """
    points = np.asarray(eye_points, dtype=float)
    if points.shape != (6, 2):
        raise ValueError("eye_points must have shape (6, 2)")

    p1, p2, p3, p4, p5, p6 = points
    horizontal = np.linalg.norm(p1 - p4)
    if horizontal == 0:
        raise ValueError("horizontal eye width must be non-zero")
    return float((np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / (2 * horizontal))


def calculate_eye_ears(landmarks: EyeLandmarks) -> tuple[float, float, float]:
    """Return left, right, and mean EAR for one face observation."""
    left = calculate_ear(_eye_array(landmarks.left_eye))
    right = calculate_ear(_eye_array(landmarks.right_eye))
    return left, right, (left + right) / 2.0
