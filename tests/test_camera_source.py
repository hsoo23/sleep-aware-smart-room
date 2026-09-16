from collections import deque

import pytest

from sleep_aware.capture import (
    CameraClosedError,
    CameraOpenError,
    CameraReadError,
    FakeFrameSource,
    OpenCVCameraSource,
)
from sleep_aware.pipeline import Frame


class FakeCapture:
    def __init__(self, *, opened=True, reads=()) -> None:
        """Create a controllable stand-in for OpenCV VideoCapture."""
        self.opened = opened
        self.reads = deque(reads)
        self.properties = []
        self.release_count = 0

    def isOpened(self):
        """Return the configured camera-open state."""
        return self.opened

    def set(self, property_id, value):
        """Record a requested capture property."""
        self.properties.append((property_id, value))
        return True

    def read(self):
        """Return the next configured capture result."""
        return self.reads.popleft()

    def release(self):
        """Record each request to release the capture."""
        self.release_count += 1


class FakeOpenCV:
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4

    def __init__(self, capture):
        """Expose one fake capture through an OpenCV-shaped API."""
        self.capture = capture
        self.requested_indices = []

    def VideoCapture(self, camera_index):
        """Record the requested index and return the fake capture."""
        self.requested_indices.append(camera_index)
        return self.capture


def test_camera_uses_configured_index_and_resolution():
    """The adapter forwards non-default camera settings to OpenCV."""
    capture = FakeCapture()
    opencv = FakeOpenCV(capture)

    source = OpenCVCameraSource(
        camera_index=2,
        width=1280,
        height=720,
        opencv=opencv,
    )

    assert source.camera_index == 2
    assert opencv.requested_indices == [2]
    assert capture.properties == [
        (opencv.CAP_PROP_FRAME_WIDTH, 1280),
        (opencv.CAP_PROP_FRAME_HEIGHT, 720),
    ]
    source.close()


def test_camera_frames_have_sequence_and_monotonic_timestamp():
    """Successful reads receive ordered sequence numbers and clock values."""
    first_payload = object()
    second_payload = object()
    capture = FakeCapture(reads=[(True, first_payload), (True, second_payload)])
    timestamps = iter([10.25, 10.75])
    source = OpenCVCameraSource(
        camera_index=4,
        clock=lambda: next(timestamps),
        opencv=FakeOpenCV(capture),
    )

    first = source.read()
    second = source.read()

    assert first == Frame(sequence=0, timestamp=10.25, payload=first_payload)
    assert second == Frame(sequence=1, timestamp=10.75, payload=second_payload)
    source.close()


def test_open_failure_has_distinct_error_and_releases_capture():
    """An unavailable camera raises CameraOpenError and is released."""
    capture = FakeCapture(opened=False)

    with pytest.raises(CameraOpenError, match="camera index 8"):
        OpenCVCameraSource(camera_index=8, opencv=FakeOpenCV(capture))

    assert capture.release_count == 1


@pytest.mark.parametrize("read_result", [(False, object()), (True, None)])
def test_read_failure_has_distinct_error(read_result):
    """Invalid OpenCV read results raise CameraReadError and release once."""
    capture = FakeCapture(reads=[read_result])
    source = OpenCVCameraSource(camera_index=1, opencv=FakeOpenCV(capture))

    with pytest.raises(CameraReadError, match="failed to read frame 0"):
        source.read()

    assert capture.release_count == 1
    source.close()
    assert capture.release_count == 1


def test_normal_context_manager_exit_releases_capture():
    """A normal context-manager exit releases the camera."""
    capture = FakeCapture()

    with OpenCVCameraSource(camera_index=0, opencv=FakeOpenCV(capture)):
        pass

    assert capture.release_count == 1


def test_context_manager_always_releases_capture():
    """An exceptional exit releases once and prevents subsequent reads."""
    capture = FakeCapture()

    with pytest.raises(RuntimeError, match="stop"):
        with OpenCVCameraSource(camera_index=0, opencv=FakeOpenCV(capture)) as source:
            assert source.camera_index == 0
            raise RuntimeError("stop")

    assert capture.release_count == 1
    source.close()
    assert capture.release_count == 1
    with pytest.raises(CameraClosedError):
        source.read()


def test_fake_source_returns_finite_frame_sequence():
    """The reusable fake returns supplied frames followed by ``None``."""
    frames = [Frame(3, 1.0, object()), Frame(4, 2.0, object())]
    source = FakeFrameSource(frames)

    assert [source.read(), source.read(), source.read()] == [*frames, None]
