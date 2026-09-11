import pytest

from sleep_aware.detection.adaptive_ear import AdaptiveEarCalibrator
from sleep_aware.detection.perclos import PerclosWindow


def test_adaptive_threshold_uses_personal_baseline():
    calibrator = AdaptiveEarCalibrator(multiplier=0.75, minimum_samples=3)
    for ear in (0.30, 0.34, 0.32):
        calibrator.add(ear)

    assert calibrator.ready
    assert calibrator.baseline == pytest.approx(0.32)
    assert calibrator.threshold == pytest.approx(0.24)


def test_perclos_removes_observations_outside_window():
    window = PerclosWindow(window_seconds=10.0)
    window.update(0.0, True)
    window.update(5.0, False)
    assert window.update(10.0, True) == pytest.approx(2 / 3)
    assert window.update(11.0, False) == pytest.approx(1 / 3)
