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
    "MediaPipeFaceMeshProcessor",
    "PipelineEvent",
    "Point",
]
