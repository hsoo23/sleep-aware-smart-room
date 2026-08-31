"""Personal baseline calibration for adaptive EAR thresholding."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median


@dataclass
class AdaptiveEarCalibrator:
    """Estimate a personal threshold from normal open-eye EAR samples.

    The multiplier is intentionally explicit so it can be tuned only on the
    development participants and then frozen for subject-independent tests.
    """

    multiplier: float = 0.75
    minimum_samples: int = 90
    samples: list[float] = field(default_factory=list)

    def add(self, ear: float) -> None:
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

