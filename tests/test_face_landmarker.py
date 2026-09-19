"""Tasks Face Landmarker adapter and backend selection, verified without MediaPipe."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from sleep_aware.pipeline import (
    LEFT_EYE_INDICES,
    RIGHT_EYE_INDICES,
    FaceMeshProcessingError,
    Frame,
    MediaPipeFaceLandmarkerProcessor,
    MediaPipeFaceMeshProcessor,
    available_backend,
    create_landmark_processor,
)
from sleep_aware.pipeline.face_landmarker import DOWNLOAD_HINT, download_model


class FakeCv2:
    COLOR_BGR2RGB = 4

    @staticmethod
    def cvtColor(image, conversion):
        assert conversion == FakeCv2.COLOR_BGR2RGB
        return image[..., ::-1].copy()


class FakeLandmarker:
    def __init__(self, results):
        self.results = list(results)
        self.timestamps = []
        self.closed = False

    def detect_for_video(self, image, timestamp_ms):
        self.timestamps.append(timestamp_ms)
        return self.results.pop(0)

    def close(self):
        self.closed = True


def _processor(results, **overrides):
    landmarker = FakeLandmarker(results)
    options = {}

    def factory(**kwargs):
        options.update(kwargs)
        return landmarker

    processor = MediaPipeFaceLandmarkerProcessor(
        model_path="unused-in-tests.task",
        cv2_module=FakeCv2,
        landmarker_factory=factory,
        image_factory=lambda rgb: rgb,
        **overrides,
    )
    return processor, landmarker, options


def _landmarks(count=478):
    return [SimpleNamespace(x=index / 1000, y=index / 2000) for index in range(count)]


def _frame(sequence=4):
    return Frame(sequence, 1.0, np.zeros((100, 200, 3), dtype=np.uint8))


def test_tasks_backend_produces_the_same_pixel_geometry_as_face_mesh():
    landmarks = _landmarks()
    processor, _, options = _processor([SimpleNamespace(face_landmarks=[landmarks])])

    result = processor.process(_frame())

    assert result is not None
    assert tuple(point.x for point in result.left_eye) == pytest.approx(
        tuple(index / 5 for index in LEFT_EYE_INDICES)
    )
    assert tuple(point.y for point in result.right_eye) == pytest.approx(
        tuple(index / 20 for index in RIGHT_EYE_INDICES)
    )
    assert len(result.face_landmarks) == 478
    assert options == {
        "model_path": "unused-in-tests.task",
        "max_num_faces": 1,
        "min_detection_confidence": 0.5,
        "min_tracking_confidence": 0.5,
    }


def test_no_face_is_reported_as_none():
    processor, _, _ = _processor([SimpleNamespace(face_landmarks=[])])

    assert processor.process(_frame()) is None


def test_video_mode_timestamps_strictly_increase():
    results = [SimpleNamespace(face_landmarks=[_landmarks()]) for _ in range(3)]
    processor, landmarker, _ = _processor(results, clock=lambda: 10.0)

    for sequence in range(3):
        processor.process(_frame(sequence))

    assert landmarker.timestamps == sorted(set(landmarker.timestamps))
    assert landmarker.timestamps[0] == 10_000


def test_processing_failure_is_wrapped_with_the_frame_sequence():
    class Broken(FakeLandmarker):
        def detect_for_video(self, image, timestamp_ms):
            raise OSError("native failure")

    landmarker = Broken([])
    processor = MediaPipeFaceLandmarkerProcessor(
        model_path="unused-in-tests.task",
        cv2_module=FakeCv2,
        landmarker_factory=lambda **kwargs: landmarker,
        image_factory=lambda rgb: rgb,
    )

    with pytest.raises(FaceMeshProcessingError, match="frame sequence 7"):
        processor.process(_frame(7))


def test_closed_processor_refuses_further_frames():
    processor, landmarker, _ = _processor([])

    processor.close()
    processor.close()

    assert landmarker.closed
    with pytest.raises(FaceMeshProcessingError, match="closed"):
        processor.process(_frame())


def test_missing_model_file_explains_how_to_get_it(tmp_path):
    with pytest.raises(RuntimeError, match="FACE_LANDMARKER_MODEL"):
        MediaPipeFaceLandmarkerProcessor(model_path=tmp_path / "absent.task")

    assert "--download" in DOWNLOAD_HINT


def test_download_model_writes_the_file_atomically(tmp_path, monkeypatch):
    class FakeResponse:
        def read(self):
            return b"model-bytes"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

    monkeypatch.setattr(
        "sleep_aware.pipeline.face_landmarker.urllib.request.urlopen",
        lambda url: FakeResponse(),
    )
    destination = tmp_path / "models" / "face_landmarker.task"

    path = download_model(destination)

    assert path.read_bytes() == b"model-bytes"
    assert list(tmp_path.glob("models/*.partial")) == []


@pytest.mark.parametrize(
    ("module", "expected"),
    [
        (SimpleNamespace(solutions=object(), tasks=object()), "solutions"),
        (SimpleNamespace(tasks=object()), "tasks"),
    ],
)
def test_available_backend_follows_the_installed_mediapipe(module, expected):
    assert available_backend(module) == expected


def test_factory_builds_the_legacy_processor_when_solutions_exist(monkeypatch):
    built = {}
    monkeypatch.setattr(
        "sleep_aware.pipeline.landmarks.MediaPipeFaceMeshProcessor",
        lambda **kwargs: built.setdefault("face_mesh", kwargs),
    )

    create_landmark_processor(model_path="ignored.task", backend="solutions")

    assert built["face_mesh"]["refine_landmarks"] is True


def test_factory_builds_the_tasks_processor_when_solutions_are_gone(monkeypatch):
    built = {}
    monkeypatch.setattr(
        "sleep_aware.pipeline.landmarks.MediaPipeFaceLandmarkerProcessor",
        lambda **kwargs: built.setdefault("tasks", kwargs),
    )

    create_landmark_processor(model_path="model.task", backend_resolver=lambda: "tasks")

    assert built["tasks"]["model_path"] == "model.task"
    # refine_landmarks has no Tasks equivalent; the model always returns 478 points.
    assert "refine_landmarks" not in built["tasks"]


def test_both_processors_are_exported():
    assert MediaPipeFaceMeshProcessor is not MediaPipeFaceLandmarkerProcessor
