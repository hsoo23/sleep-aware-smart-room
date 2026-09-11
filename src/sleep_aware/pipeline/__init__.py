"""Hardware-independent contracts and orchestration for the baseline pipeline."""

from .contracts import (
    ActionExecutor,
    DrowsinessDetector,
    EventLogger,
    FrameSource,
    LandmarkProcessor,
)
from .models import ActionResult, EyeLandmarks, Frame, PipelineEvent, Point
from .runner import BaselinePipeline

__all__ = [
    "ActionExecutor",
    "ActionResult",
    "BaselinePipeline",
    "DrowsinessDetector",
    "EventLogger",
    "EyeLandmarks",
    "Frame",
    "FrameSource",
    "LandmarkProcessor",
    "PipelineEvent",
    "Point",
]
