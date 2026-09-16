"""OpenCV camera adapter for the baseline pipeline."""

from __future__ import annotations

import importlib
import time
from collections.abc import Callable
from types import TracebackType
from typing import Any

from sleep_aware.pipeline.models import Frame


class CameraSourceError(RuntimeError):
    """Base class for camera source failures."""


class CameraDependencyError(CameraSourceError):
    """Raised when the optional OpenCV dependency is unavailable."""


class CameraOpenError(CameraSourceError):
    """Raised when OpenCV cannot open the configured camera."""


class CameraReadError(CameraSourceError):
    """Raised when an opened camera fails to return a frame."""


class CameraClosedError(CameraSourceError):
    """Raised when a caller reads from a source that has been closed."""


def _load_opencv() -> Any:
    """Load the optional OpenCV module with an actionable error message."""
    try:
        return importlib.import_module("cv2")
    except ImportError as error:
        raise CameraDependencyError(
            "OpenCV is required for camera capture; install the 'host' extra"
        ) from error


class OpenCVCameraSource:
    """Read timestamped frames from one configured OpenCV camera.

    Use the source as a context manager, or call :meth:`close` explicitly, so
    the underlying ``VideoCapture`` is released on every shutdown path.
    """

    def __init__(
        self,
        *,
        camera_index: int,
        width: int | None = None,
        height: int | None = None,
        clock: Callable[[], float] = time.monotonic,
        opencv: Any | None = None,
    ) -> None:
        """Open a configured camera and apply its requested resolution."""
        self._camera_index = camera_index
        self._clock = clock
        self._sequence = 0
        self._closed = False
        self._opencv = opencv if opencv is not None else _load_opencv()
        self._capture = self._opencv.VideoCapture(camera_index)

        try:
            if not self._capture.isOpened():
                raise CameraOpenError(f"failed to open camera index {camera_index}")
            if width is not None:
                self._capture.set(self._opencv.CAP_PROP_FRAME_WIDTH, width)
            if height is not None:
                self._capture.set(self._opencv.CAP_PROP_FRAME_HEIGHT, height)
        except BaseException:
            self.close()
            raise

    @property
    def camera_index(self) -> int:
        """Return the configured OpenCV camera index."""
        return self._camera_index

    def read(self) -> Frame:
        """Return the next frame, or raise a typed error when capture fails."""
        if self._closed:
            raise CameraClosedError(f"camera index {self._camera_index} is closed")

        try:
            succeeded, payload = self._capture.read()
        except Exception as error:
            self.close()
            raise CameraReadError(
                f"failed to read frame {self._sequence} from camera index {self._camera_index}"
            ) from error
        if not succeeded or payload is None:
            self.close()
            raise CameraReadError(
                f"failed to read frame {self._sequence} from camera index {self._camera_index}"
            )

        frame = Frame(
            sequence=self._sequence,
            timestamp=self._clock(),
            payload=payload,
        )
        self._sequence += 1
        return frame

    def close(self) -> None:
        """Release the underlying capture exactly once."""
        if self._closed:
            return
        self._closed = True
        self._capture.release()

    def __enter__(self) -> OpenCVCameraSource:  # noqa: PYI034
        """Return this opened source when entering a context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the camera when leaving a context manager."""
        self.close()
