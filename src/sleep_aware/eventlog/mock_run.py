"""Hardware-free baseline run that produces a schema-valid JSONL log.

Run with ``python -m sleep_aware.eventlog.mock_run``. Frames, landmarks, and
device calls are synthetic and advance a simulated monotonic clock, so the
recorded latencies exercise the logging path but are not performance data.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from sleep_aware.config import settings
from sleep_aware.control import Action, ClosedLoopPolicy, Intention
from sleep_aware.detection import AdaptiveEarDetector, TemporalDrowsinessDetector
from sleep_aware.pipeline import ActionResult, BaselinePipeline, EyeLandmarks, Frame, Point

from .jsonl import JsonlEventLogger
from .metadata import RunMetadata, git_revision, new_run_id

FPS = 30
INFERENCE_SECONDS = 0.012
ACTION_SECONDS = 0.035
OPEN_EAR_VERTICAL = 0.6  # EAR 0.30
CLOSED_EAR_VERTICAL = 0.3  # EAR 0.15
# Fixed rather than environment-backed so the scenario always reaches DROWSY and recovery.
EAR_THRESHOLD = 0.21
DROWSY_SECONDS = 2.0
RECOVERY_SECONDS = 0.5

# (seconds, eye vertical offset or None for no face)
SCENARIO: tuple[tuple[float, float | None], ...] = (
    (1.0, OPEN_EAR_VERTICAL),
    (3.0, CLOSED_EAR_VERTICAL),
    (1.0, OPEN_EAR_VERTICAL),
    (0.5, None),
    (1.0, OPEN_EAR_VERTICAL),
)


@dataclass
class SimulatedClock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _eye(vertical: float) -> tuple[Point, Point, Point, Point, Point, Point]:
    return (
        Point(0, 0),
        Point(1, vertical),
        Point(3, vertical),
        Point(4, 0),
        Point(3, -vertical),
        Point(1, -vertical),
    )


def _observations(calibration_frames: int = 0) -> Iterator[float | None]:
    for _ in range(calibration_frames):
        yield OPEN_EAR_VERTICAL
    for seconds, vertical in SCENARIO:
        for _ in range(round(seconds * FPS)):
            yield vertical


class SyntheticFrameSource:
    def __init__(self, clock: SimulatedClock, calibration_frames: int = 0) -> None:
        self._clock = clock
        self._observations = _observations(calibration_frames)
        self._sequence = 0
        self._next_capture_at = clock()

    def read(self) -> Frame | None:
        vertical = next(self._observations, False)
        if vertical is False:
            return None
        self._clock.advance(max(0.0, self._next_capture_at - self._clock()))
        frame = Frame(self._sequence, self._clock(), payload=vertical)
        self._sequence += 1
        self._next_capture_at += 1.0 / FPS
        return frame


class SyntheticLandmarkProcessor:
    def __init__(self, clock: SimulatedClock) -> None:
        self._clock = clock

    def process(self, frame: Frame) -> EyeLandmarks | None:
        self._clock.advance(INFERENCE_SECONDS)
        if frame.payload is None:
            return None
        return EyeLandmarks(_eye(frame.payload), _eye(frame.payload))


class SyntheticActionExecutor:
    """Succeeds for every action except ``failing_action``."""

    def __init__(self, clock: SimulatedClock, failing_action: Action | None) -> None:
        self._clock = clock
        self._failing_action = failing_action

    def execute(self, action: Action) -> ActionResult:
        self._clock.advance(ACTION_SECONDS)
        if action is self._failing_action:
            return ActionResult(action, succeeded=False, detail="simulated device timeout")
        return ActionResult(action, succeeded=True)


def run_mock(
    log_dir: Path | str,
    intention: Intention = Intention.WAKE,
    *,
    failing_action: Action | None = Action.LIGHT_ON,
    detector_stage: str = "b0",
    calibration_samples: int = 90,
    adaptive_multiplier: float = 0.75,
) -> Path:
    """Run the synthetic scenario and return the path of the written log."""
    clock = SimulatedClock()
    if detector_stage == "b1":
        detector = AdaptiveEarDetector(
            multiplier=adaptive_multiplier,
            minimum_samples=calibration_samples,
            drowsy_seconds=DROWSY_SECONDS,
            recovery_seconds=RECOVERY_SECONDS,
        )
        detector_config = {
            "adaptive_multiplier": detector.multiplier,
            "calibration_samples": detector.minimum_samples,
            "calibration_protocol": "synthetic-open-eyes",
        }
    elif detector_stage == "b0":
        detector = TemporalDrowsinessDetector(
            ear_threshold=EAR_THRESHOLD,
            drowsy_seconds=DROWSY_SECONDS,
            recovery_seconds=RECOVERY_SECONDS,
        )
        detector_config = {"ear_threshold": detector.ear_threshold}
    else:
        raise ValueError(f"unsupported detector stage: {detector_stage}")
    commit, dirty = git_revision(Path(__file__).resolve().parent)
    metadata = RunMetadata(
        run_id=new_run_id(),
        intention=intention,
        detector_name="B1-adaptive-ear" if detector_stage == "b1" else "B0-fixed-ear",
        detector_version="0.1.0",
        config_version="mock-adaptive-v1" if detector_stage == "b1" else "mock-fixed",
        detector_config={
            **detector_config,
            "drowsy_seconds": detector.drowsy_seconds,
            "recovery_seconds": detector.recovery_seconds,
            "source": "mock",
        },
        git_commit=commit,
        git_dirty=dirty,
    )
    with JsonlEventLogger(log_dir, metadata) as logger:
        policy = ClosedLoopPolicy()
        pipeline = BaselinePipeline(
            frame_source=SyntheticFrameSource(
                clock,
                calibration_frames=calibration_samples if detector_stage == "b1" else 0,
            ),
            landmark_processor=SyntheticLandmarkProcessor(clock),
            detector=detector,
            policy=policy,
            action_executor=SyntheticActionExecutor(clock, failing_action),
            event_logger=logger,
            intention=intention,
            clock=clock,
        )
        try:
            for _ in pipeline.run():
                pass
        finally:
            pipeline.close()
        if isinstance(detector, AdaptiveEarDetector) and not detector.ready:
            raise RuntimeError("synthetic adaptive EAR calibration did not finish")
        if policy.has_pending_cleanup:
            # Raising inside the logger context records run_end as failed.
            raise RuntimeError("mock cleanup actions did not complete")
    return logger.path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log-dir", default=settings.log_dir)
    parser.add_argument(
        "--intention", choices=[item.value for item in Intention], default=Intention.WAKE.value
    )
    parser.add_argument("--detector", choices=("b0", "b1"), default="b0")
    parser.add_argument("--calibration-samples", type=int, default=90)
    parser.add_argument("--adaptive-multiplier", type=float, default=0.75)
    args = parser.parse_args(argv)
    print(
        run_mock(
            args.log_dir,
            Intention(args.intention),
            detector_stage=args.detector,
            calibration_samples=args.calibration_samples,
            adaptive_multiplier=args.adaptive_multiplier,
        )
    )


if __name__ == "__main__":
    main()
