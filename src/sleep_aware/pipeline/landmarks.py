"""Pick the landmark backend available in the installed MediaPipe.

Wheels published before the Tasks migration expose ``mediapipe.solutions.face_mesh``;
newer ones expose only ``mediapipe.tasks``. Both backends return identical
pixel-space eye geometry, so the detector, EAR calculation, and logs do not change
with the backend.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from .face_landmarker import MediaPipeFaceLandmarkerProcessor
from .face_mesh import MediaPipeFaceMeshProcessor

Backend = Literal["solutions", "tasks"]


def available_backend(mediapipe_module: Any | None = None) -> Backend:
    """Return the landmark backend the installed MediaPipe provides."""
    if mediapipe_module is None:
        try:
            import mediapipe as mediapipe_module
        except ImportError as error:
            raise RuntimeError(
                "MediaPipe is required; install the host optional dependencies"
            ) from error
    return "solutions" if hasattr(mediapipe_module, "solutions") else "tasks"


def create_landmark_processor(
    *,
    model_path: Path | str,
    max_num_faces: int = 1,
    refine_landmarks: bool = True,
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
    backend: Backend | None = None,
    backend_resolver: Callable[[], Backend] = available_backend,
) -> MediaPipeFaceMeshProcessor | MediaPipeFaceLandmarkerProcessor:
    """Build the Face Mesh or Face Landmarker processor for this environment.

    ``refine_landmarks`` only applies to the legacy backend; the Tasks model always
    includes the refined (478-point) mesh.
    """
    if (backend or backend_resolver()) == "solutions":
        return MediaPipeFaceMeshProcessor(
            max_num_faces=max_num_faces,
            refine_landmarks=refine_landmarks,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
    return MediaPipeFaceLandmarkerProcessor(
        model_path=model_path,
        max_num_faces=max_num_faces,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    )
