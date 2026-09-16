"""MediaPipe Face Mesh adapter for the fixed-EAR baseline."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from types import ModuleType
from typing import Any

from .models import EyeLandmarks, Frame, Point

# Keep the submitted prototype's p1..p6 ordering for reproducibility.
LEFT_EYE_INDICES = (33, 160, 158, 133, 153, 144)
RIGHT_EYE_INDICES = (362, 385, 387, 263, 373, 380)


class FaceMeshProcessingError(RuntimeError):
    """Raised when a frame cannot be processed reliably.

    A normal no-face observation is represented by ``None`` instead.
    """


class MediaPipeFaceMeshProcessor:
    """Extract the two ordered six-point eye geometries from BGR frames.

    Optional OpenCV and MediaPipe imports are delayed until construction so the
    hardware-independent core and its tests do not require host dependencies.
    """

    def __init__(
        self,
        *,
        max_num_faces: int = 1,
        refine_landmarks: bool = True,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        cv2_module: ModuleType | Any | None = None,
        face_mesh_factory: Callable[..., Any] | None = None,
    ) -> None:
        if cv2_module is None:
            try:
                import cv2 as cv2_module
            except ImportError as error:
                raise RuntimeError(
                    "OpenCV is required; install the host optional dependencies"
                ) from error
        if face_mesh_factory is None:
            try:
                import mediapipe as mp
            except ImportError as error:
                raise RuntimeError(
                    "MediaPipe is required; install the host optional dependencies"
                ) from error
            face_mesh_factory = mp.solutions.face_mesh.FaceMesh

        self._cv2 = cv2_module
        self._face_mesh = face_mesh_factory(
            max_num_faces=max_num_faces,
            refine_landmarks=refine_landmarks,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._closed = False

    def process(self, frame: Frame) -> EyeLandmarks | None:
        """Return eye landmarks, ``None`` for no face, or raise on bad processing."""
        if self._closed:
            raise FaceMeshProcessingError("Face Mesh processor is closed")

        image = frame.payload
        try:
            height, width = image.shape[:2]
            if height <= 0 or width <= 0:
                raise ValueError("frame dimensions must be positive")
            rgb_frame = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False
            result = self._face_mesh.process(rgb_frame)
        except Exception as error:
            raise FaceMeshProcessingError(
                f"failed to process frame sequence {frame.sequence}"
            ) from error

        try:
            faces = result.multi_face_landmarks
        except AttributeError as error:
            raise FaceMeshProcessingError(
                f"invalid result for frame sequence {frame.sequence}"
            ) from error
        if not faces:
            return None

        try:
            landmarks = faces[0].landmark
            return EyeLandmarks(
                left_eye=self._points(landmarks, LEFT_EYE_INDICES, width, height),
                right_eye=self._points(landmarks, RIGHT_EYE_INDICES, width, height),
                face_landmarks=tuple(
                    Point(float(landmark.x * width), float(landmark.y * height))
                    for landmark in landmarks
                ),
            )
        except (IndexError, TypeError, AttributeError) as error:
            raise FaceMeshProcessingError(
                f"invalid landmarks for frame sequence {frame.sequence}"
            ) from error

    @staticmethod
    def _points(
        landmarks: Sequence[Any],
        indices: tuple[int, int, int, int, int, int],
        width: int,
        height: int,
    ) -> tuple[Point, Point, Point, Point, Point, Point]:
        # Pixel-space geometry preserves EAR under non-square camera frames and
        # matches the legacy implementation's coordinate system.
        return tuple(
            Point(float(landmarks[index].x * width), float(landmarks[index].y * height))
            for index in indices
        )  # type: ignore[return-value]

    def close(self) -> None:
        """Release MediaPipe native resources; repeated calls are safe."""
        if not self._closed:
            self._face_mesh.close()
            self._closed = True

    def __enter__(self) -> MediaPipeFaceMeshProcessor:  # noqa: PYI034
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()
