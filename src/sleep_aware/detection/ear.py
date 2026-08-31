"""Eye Aspect Ratio feature calculation."""

from __future__ import annotations

import numpy as np


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

