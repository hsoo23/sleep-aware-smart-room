"""MediaPipe Tasks Face Landmarker adapter for the fixed-EAR baseline.

Recent MediaPipe wheels ship only the Tasks API; the legacy ``mediapipe.solutions``
Face Mesh module is gone. This adapter produces the same pixel-space eye geometry
as :class:`~sleep_aware.pipeline.face_mesh.MediaPipeFaceMeshProcessor`, so the EAR
calculation, landmark indices, and detector stay unchanged.
"""

from __future__ import annotations

import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

from .face_mesh import FaceMeshProcessingError, eye_landmarks_from
from .models import EyeLandmarks, Frame

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
MODEL_FILENAME = "face_landmarker.task"
DOWNLOAD_HINT = (
    "Face Landmarker model not found. "
    "Download it with python -m sleep_aware.pipeline.face_landmarker --download "
    "or set its path with FACE_LANDMARKER_MODEL"
)


DOWNLOAD_TIMEOUT_SECONDS = 60.0


def download_model(
    destination: Path | str,
    *,
    url: str = MODEL_URL,
    timeout: float = DOWNLOAD_TIMEOUT_SECONDS,
) -> Path:
    """Download the Face Landmarker model; the binary is never committed."""
    path = Path(destination).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Written to a temporary name first so an interrupted download is not reused.
    partial = path.with_suffix(path.suffix + ".partial")
    with (  # noqa: S310 - fixed https model URL
        urllib.request.urlopen(url, timeout=timeout) as response,
        partial.open("wb") as target,
    ):
        target.write(response.read())
    partial.replace(path)
    return path


class MediaPipeFaceLandmarkerProcessor:
    """Extract ordered six-point eye geometries using the MediaPipe Tasks API."""

    def __init__(
        self,
        *,
        model_path: Path | str,
        max_num_faces: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        cv2_module: ModuleType | Any | None = None,
        landmarker_factory: Callable[..., Any] | None = None,
        image_factory: Callable[[Any], Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        # ``~`` and relative paths come from the CLI, the environment, and callers,
        # so normalize once and use the same path for the check and the backend.
        path = Path(model_path).expanduser().resolve()
        if landmarker_factory is None and not path.is_file():
            raise RuntimeError(f"{DOWNLOAD_HINT} (checked path: {path})")

        if cv2_module is None:
            try:
                import cv2 as cv2_module
            except ImportError as error:
                raise RuntimeError(
                    "OpenCV is required; install the host optional dependencies"
                ) from error

        if landmarker_factory is None or image_factory is None:
            tasks_factory, tasks_image = _default_tasks_backend()
            landmarker_factory = landmarker_factory or tasks_factory
            image_factory = image_factory or tasks_image

        self._cv2 = cv2_module
        self._image_factory = image_factory
        self._clock = clock
        self._last_timestamp_ms = -1
        self._landmarker = landmarker_factory(
            model_path=str(path),
            max_num_faces=max_num_faces,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._closed = False

    def process(self, frame: Frame) -> EyeLandmarks | None:
        """Return eye landmarks, ``None`` for no face, or raise on bad processing."""
        if self._closed:
            raise FaceMeshProcessingError("Face Landmarker processor is closed")

        image = frame.payload
        try:
            height, width = image.shape[:2]
            if height <= 0 or width <= 0:
                raise ValueError("frame dimensions must be positive")
            rgb_frame = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2RGB)
            result = self._landmarker.detect_for_video(
                self._image_factory(rgb_frame), self._next_timestamp_ms()
            )
        except Exception as error:
            raise FaceMeshProcessingError(
                f"failed to process frame sequence {frame.sequence}"
            ) from error

        try:
            faces = result.face_landmarks
        except AttributeError as error:
            raise FaceMeshProcessingError(
                f"invalid result for frame sequence {frame.sequence}"
            ) from error
        if not faces:
            return None

        try:
            return eye_landmarks_from(faces[0], width, height)
        except (IndexError, TypeError, AttributeError) as error:
            raise FaceMeshProcessingError(
                f"invalid landmarks for frame sequence {frame.sequence}"
            ) from error

    def _next_timestamp_ms(self) -> int:
        """Return a strictly increasing timestamp, as the VIDEO mode requires."""
        timestamp_ms = max(int(self._clock() * 1000), self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        return timestamp_ms

    def close(self) -> None:
        """Release MediaPipe native resources; repeated calls are safe."""
        if not self._closed:
            self._landmarker.close()
            self._closed = True

    def __enter__(self) -> MediaPipeFaceLandmarkerProcessor:  # noqa: PYI034
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def _default_tasks_backend() -> tuple[Callable[..., Any], Callable[[Any], Any]]:
    """Build the Tasks landmarker and image factories from the installed MediaPipe."""
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import (
            FaceLandmarker,
            FaceLandmarkerOptions,
            RunningMode,
        )
    except ImportError as error:
        raise RuntimeError(
            "MediaPipe Tasks is required; install the host optional dependencies"
        ) from error

    def landmarker_factory(
        *,
        model_path: str,
        max_num_faces: int,
        min_detection_confidence: float,
        min_tracking_confidence: float,
    ) -> Any:
        return FaceLandmarker.create_from_options(
            FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=model_path),
                running_mode=RunningMode.VIDEO,
                num_faces=max_num_faces,
                min_face_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
        )

    def image_factory(rgb_frame: Any) -> Any:
        import numpy as np

        return mp.Image(
            image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb_frame)
        )

    return landmarker_factory, image_factory


def main(argv: list[str] | None = None) -> int:
    import argparse

    from sleep_aware.config import settings

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the Face Landmarker model",
    )
    parser.add_argument("--model-path", default=settings.face_landmarker_model)
    args = parser.parse_args(argv)

    if not args.download:
        parser.error("Specify --download")
    print(download_model(args.model_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
