"""Personal baseline calibration for adaptive EAR thresholding."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median

from .state import DrowsinessState, TemporalDrowsinessDetector


@dataclass
class AdaptiveEarCalibrator:
    """Estimate a personal threshold from normal open-eye EAR samples.

    The multiplier is intentionally explicit so it can be tuned only on the
    development participants and then frozen for subject-independent tests.
    """

    multiplier: float = 0.75
    minimum_samples: int = 90
    samples: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not math.isfinite(self.multiplier) or not 0 < self.multiplier < 1:
            raise ValueError("adaptive EAR multiplier must be between 0 and 1")
        if self.minimum_samples < 1:
            raise ValueError("minimum_samples must be positive")

    def add(self, ear: float) -> None:
        if not math.isfinite(ear):
            raise ValueError("calibration EAR must be finite")
        if ear > 0:
            self.samples.append(float(ear))

    @property
    def ready(self) -> bool:
        return len(self.samples) >= self.minimum_samples

    @property
    def baseline(self) -> float:
        if not self.ready:
            raise RuntimeError("not enough baseline samples")
        return float(median(self.samples))

    @property
    def threshold(self) -> float:
        return self.baseline * self.multiplier


@dataclass
class AdaptiveEarDetector:
    """Calibrate on guided open-eye frames, then apply a fixed personal threshold.

    The caller must instruct the user to keep their eyes normally open during
    calibration. EAR alone cannot verify that those frames are truly open-eye
    ground truth. Calibration frames are marked by ``ear_threshold=None`` and
    must be excluded from detection-performance calculations.
    """

    multiplier: float = 0.75
    minimum_samples: int = 90
    drowsy_seconds: float = 2.0
    recovery_seconds: float = 0.5
    _calibrator: AdaptiveEarCalibrator = field(init=False, repr=False)
    _temporal: TemporalDrowsinessDetector = field(init=False, repr=False)
    _threshold: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._calibrator = AdaptiveEarCalibrator(self.multiplier, self.minimum_samples)
        self._temporal = TemporalDrowsinessDetector(
            drowsy_seconds=self.drowsy_seconds,
            recovery_seconds=self.recovery_seconds,
        )

    @property
    def ear_threshold(self) -> float | None:
        return self._threshold

    @property
    def ready(self) -> bool:
        return self._threshold is not None

    @property
    def calibration_sample_count(self) -> int:
        return len(self._calibrator.samples)

    @property
    def personal_baseline(self) -> float:
        return self._calibrator.baseline

    def reset(self) -> None:
        self._calibrator = AdaptiveEarCalibrator(self.multiplier, self.minimum_samples)
        self._temporal.reset()
        self._threshold = None

    def update(self, timestamp: float, ear: float | None) -> DrowsinessState:
        if self._threshold is None:
            if ear is None:
                return DrowsinessState.NO_FACE
            if not self._calibrator.ready:
                self._calibrator.add(ear)
                # AWAKE is a policy-safe placeholder during instructed open-eye
                # calibration, not a scored detector prediction.
                return DrowsinessState.AWAKE
            self._threshold = self._calibrator.threshold
            self._temporal.ear_threshold = self._threshold
        return self._temporal.update(timestamp, ear)
