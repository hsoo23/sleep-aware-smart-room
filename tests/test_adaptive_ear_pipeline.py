"""B1 calibration, pipeline, and versioned-log behavior without physical hardware."""

from __future__ import annotations

import json
import time

import pytest

from sleep_aware.cli import main
from sleep_aware.control import Intention
from sleep_aware.detection import AdaptiveEarCalibrator, AdaptiveEarDetector, DrowsinessState
from sleep_aware.eventlog.mock_run import run_mock
from sleep_aware.eventlog.schema import SCHEMA_VERSION, validate_record
from sleep_aware.pipeline import EyeLandmarks, Frame, Point


def test_adaptive_detector_calibrates_then_freezes_a_personal_threshold():
    detector = AdaptiveEarDetector(multiplier=0.75, minimum_samples=3)

    assert detector.update(0.0, None) is DrowsinessState.NO_FACE
    for timestamp, ear in ((1.0, 0.30), (2.0, 0.34), (3.0, 0.32)):
        assert detector.update(timestamp, ear) is DrowsinessState.AWAKE
        assert detector.ear_threshold is None
    assert detector.calibration_sample_count == 3
    assert not detector.ready

    assert detector.update(4.0, 0.30) is DrowsinessState.AWAKE
    assert detector.ready
    assert detector.personal_baseline == pytest.approx(0.32)
    assert detector.ear_threshold == pytest.approx(0.24)
    assert detector.update(5.0, 0.20) is DrowsinessState.EYES_CLOSED
    assert detector.update(7.0, 0.20) is DrowsinessState.DROWSY
    assert detector.update(7.5, 0.30) is DrowsinessState.DROWSY
    assert detector.update(8.0, 0.30) is DrowsinessState.AWAKE
    assert detector.ear_threshold == pytest.approx(0.24)

    detector.reset()
    assert not detector.ready
    assert detector.calibration_sample_count == 0
    assert detector.ear_threshold is None


def test_calibration_rejects_bad_configuration_and_nonfinite_ear():
    with pytest.raises(ValueError, match="multiplier"):
        AdaptiveEarCalibrator(multiplier=1.0)
    with pytest.raises(ValueError, match="minimum_samples"):
        AdaptiveEarDetector(minimum_samples=0)
    with pytest.raises(ValueError, match="finite"):
        AdaptiveEarCalibrator().add(float("nan"))


def test_b1_mock_log_marks_calibration_and_preserves_closed_loop(tmp_path):
    path = run_mock(
        tmp_path,
        Intention.WAKE,
        failing_action=None,
        detector_stage="b1",
        calibration_samples=3,
        adaptive_multiplier=0.75,
    )
    records = [json.loads(line) for line in path.read_text().splitlines()]
    for record in records:
        validate_record(record)

    start, *frames, end = records
    assert start["detector_name"] == "B1-adaptive-ear"
    assert start["schema_version"] == SCHEMA_VERSION
    assert start["detector_config"]["calibration_protocol"] == "synthetic-open-eyes"
    assert start["detector_config"]["calibration_samples"] == 3
    assert [frame["ear_threshold"] for frame in frames[:3]] == [None] * 3
    assert all(not frame["actions"] for frame in frames[:3])
    assert all(frame["ear_threshold"] == pytest.approx(0.225) for frame in frames[3:])
    assert [action["action"] for frame in frames for action in frame["actions"]] == [
        "pause_media",
        "light_on",
        "buzzer_alert",
        "play_media",
    ]
    assert (end["status"], end["frame_count"]) == ("completed", len(frames))


def test_b0_log_remains_readable_as_schema_1_0(tmp_path):
    path = run_mock(tmp_path, Intention.SLEEP, failing_action=None)
    records = [json.loads(line) for line in path.read_text().splitlines()]

    for record in records:
        validate_record({**record, "schema_version": "1.0"})
    with pytest.raises(ValueError, match="unsupported detector_config keys"):
        validate_record(
            {
                **records[0],
                "schema_version": "1.0",
                "detector_config": {"calibration_samples": 3},
            }
        )


def test_b1_camera_run_fails_clearly_if_calibration_never_finishes(tmp_path, capsys, monkeypatch):
    class EmptyCamera:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def read(self):
            return None

        def process(self, frame):
            return None

    monkeypatch.setattr("sleep_aware.cli.OpenCVCameraSource", EmptyCamera)
    monkeypatch.setattr("sleep_aware.cli.create_landmark_processor", lambda **kwargs: EmptyCamera())

    result = main(
        [
            "--input",
            "camera",
            "--actions",
            "mock",
            "--detector",
            "b1",
            "--calibration-samples",
            "3",
            "--no-display",
            "--log-dir",
            str(tmp_path),
        ]
    )

    assert result == 1
    assert "Adaptive EAR calibration incomplete: 0/3" in capsys.readouterr().out
    (path,) = tmp_path.glob("*.jsonl")
    end = json.loads(path.read_text().splitlines()[-1])
    assert (end["status"], end["error_type"]) == ("failed", "RuntimeError")


def test_b1_camera_cli_reaches_detection_and_recovery_with_fake_frames(
    tmp_path, capsys, monkeypatch
):
    base = time.monotonic() - 10.0
    observations = [
        (0.0, 0.6),
        (0.1, 0.6),  # two instructed open-eye calibration frames
        (0.2, 0.6),  # first classified frame activates the personal threshold
        (1.0, 0.3),
        (3.0, 0.3),
        (4.0, 0.6),
        (4.6, 0.6),
    ]

    class Camera:
        def __init__(self, **kwargs):
            self.frames = iter(
                Frame(i, base + offset, vertical)
                for i, (offset, vertical) in enumerate(observations)
            )

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def read(self):
            return next(self.frames, None)

    class Processor:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def process(self, frame):
            vertical = frame.payload
            eye = (
                Point(0, 0),
                Point(1, vertical),
                Point(3, vertical),
                Point(4, 0),
                Point(3, -vertical),
                Point(1, -vertical),
            )
            return EyeLandmarks(eye, eye)

    monkeypatch.setattr("sleep_aware.cli.OpenCVCameraSource", Camera)
    monkeypatch.setattr("sleep_aware.cli.create_landmark_processor", lambda **kwargs: Processor())

    result = main(
        [
            "--input",
            "camera",
            "--actions",
            "mock",
            "--detector",
            "b1",
            "--calibration-samples",
            "2",
            "--no-display",
            "--log-dir",
            str(tmp_path),
        ]
    )

    assert result == 0
    path = tmp_path / capsys.readouterr().out.strip().split("/")[-1]
    records = [json.loads(line) for line in path.read_text().splitlines()]
    frames = [row for row in records if row["record_type"] == "frame"]
    assert [row["ear_threshold"] for row in frames[:2]] == [None, None]
    assert frames[2]["ear_threshold"] == pytest.approx(0.225)
    assert [row["state"] for row in frames] == [
        "AWAKE",
        "AWAKE",
        "AWAKE",
        "EYES_CLOSED",
        "DROWSY",
        "DROWSY",
        "AWAKE",
    ]
    assert [action["action"] for row in frames for action in row["actions"]] == [
        "pause_media",
        "light_on",
        "buzzer_alert",
        "play_media",
    ]
    assert records[-1]["status"] == "completed"
