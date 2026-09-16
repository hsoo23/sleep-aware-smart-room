"""Hardware-independent contracts and orchestration for the baseline pipeline."""

from .contracts import (
    ActionExecutor,
    DrowsinessDetector,
    EventLogger,
    FrameSource,
    LandmarkProcessor,
)
from .face_mesh import (
    LEFT_EYE_INDICES,
    RIGHT_EYE_INDICES,
    FaceMeshProcessingError,
    MediaPipeFaceMeshProcessor,
)
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
    "ActionExecutor",
    "ActionResult",
    "BaselinePipeline",
    "DrowsinessDetector",
    "EventLogger",
    "FaceMeshProcessingError",
    "EyeLandmarks",
    "Frame",
    "FrameSource",
    "LEFT_EYE_INDICES",
    "LandmarkProcessor",
    "MediaPipeFaceMeshProcessor",
    "LatencyBreakdown",
    "PipelineEvent",
    "Point",
    "RIGHT_EYE_INDICES",
]
