"""Frame sources for production capture and hardware-free tests."""

from .camera import (
    CameraClosedError,
    CameraDependencyError,
    CameraOpenError,
    CameraReadError,
    CameraSourceError,
    OpenCVCameraSource,
)
from .fake import FakeFrameSource

__all__ = [
    "CameraClosedError",
    "CameraDependencyError",
    "CameraOpenError",
    "CameraReadError",
    "CameraSourceError",
    "FakeFrameSource",
    "OpenCVCameraSource",
]
