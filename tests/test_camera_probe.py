"""Camera selection helpers, verified with a fake OpenCV module."""

from __future__ import annotations

import numpy as np
import pytest

from sleep_aware.capture import smoke


class FakeCapture:
    def __init__(self, *, opened: bool, brightness: float) -> None:
        self.opened = opened
        self.brightness = brightness
        self.released = 0

    def isOpened(self):  # noqa: N802 - OpenCV spelling.
        return self.opened

    def set(self, property_id, value):
        return True

    def read(self):
        frame = np.full((4, 4, 3), self.brightness, dtype=np.uint8)
        return True, frame

    def release(self):
        self.released += 1


class FakeOpenCV:
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4

    def __init__(self, captures) -> None:
        self.captures = captures

    def VideoCapture(self, camera_index):  # noqa: N802 - OpenCV spelling.
        return self.captures[camera_index]


@pytest.fixture
def fake_opencv(monkeypatch):
    def install(captures):
        opencv = FakeOpenCV(captures)
        monkeypatch.setattr(smoke, "_load_opencv", lambda: opencv, raising=False)
        monkeypatch.setattr(
            "sleep_aware.capture.camera._load_opencv", lambda: opencv
        )
        return opencv

    return install


def test_probe_reports_each_index_with_its_brightness(fake_opencv):
    fake_opencv(
        [
            FakeCapture(opened=True, brightness=0),
            FakeCapture(opened=True, brightness=120),
        ]
    )

    reports = smoke.probe_cameras(max_index=1, width=640, height=480, frames=2)

    assert [report["index"] for report in reports] == [0, 1]
    assert reports[0]["mean_brightness"] == pytest.approx(0.0)
    assert reports[1]["mean_brightness"] == pytest.approx(120.0)
    assert all(report["usable"] for report in reports)


def test_probe_keeps_going_after_an_unusable_index(fake_opencv):
    fake_opencv(
        [
            FakeCapture(opened=False, brightness=0),
            FakeCapture(opened=True, brightness=90),
        ]
    )

    reports = smoke.probe_cameras(max_index=1, width=640, height=480, frames=1)

    assert reports[0]["usable"] is False
    assert "failed to open camera index 0" in reports[0]["detail"]
    assert reports[1]["usable"] is True


def test_black_frames_are_called_out_in_the_listing(capsys, fake_opencv):
    fake_opencv([FakeCapture(opened=True, brightness=0)])

    smoke._print_reports(
        smoke.probe_cameras(max_index=0, width=640, height=480, frames=1)
    )

    assert "black frame" in capsys.readouterr().out


def test_bright_frames_are_not_flagged(capsys, fake_opencv):
    fake_opencv([FakeCapture(opened=True, brightness=200)])

    smoke._print_reports(
        smoke.probe_cameras(max_index=0, width=640, height=480, frames=1)
    )

    assert "black frame" not in capsys.readouterr().out
