"""Hardware-independent contracts and orchestration for the baseline pipeline."""

from .contracts import (
    ActionExecutor,
    DrowsinessDetector,
    EventLogger,
    FrameSource,
    LandmarkProcessor,
)
from .face_landmarker import MediaPipeFaceLandmarkerProcessor, download_model
from .face_mesh import (
    LEFT_EYE_INDICES,
    RIGHT_EYE_INDICES,
    FaceMeshProcessingError,
    MediaPipeFaceMeshProcessor,
    eye_landmarks_from,
)
from .landmarks import available_backend, create_landmark_processor
from .models import (
    ActionResult,
    EyeLandmarks,
    Frame,
    LatencyBreakdown,
    PipelineEvent,
    Point,
)
from .runner import BaselinePipeline

__all__ = [
    "LEFT_EYE_INDICES",
    "RIGHT_EYE_INDICES",
    "ActionExecutor",
    "ActionResult",
    "BaselinePipeline",
    "DrowsinessDetector",
    "EventLogger",
    "EyeLandmarks",
    "FaceMeshProcessingError",
    "Frame",
    "FrameSource",
    "LandmarkProcessor",
    "LatencyBreakdown",
    "MediaPipeFaceLandmarkerProcessor",
    "MediaPipeFaceMeshProcessor",
    "available_backend",
    "create_landmark_processor",
    "download_model",
    "eye_landmarks_from",
    "PipelineEvent",
    "Point",
]
