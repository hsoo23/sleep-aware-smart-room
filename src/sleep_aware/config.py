"""Environment-backed configuration shared by host and Raspberry Pi services."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    pi_base_url: str = os.getenv("PI_BASE_URL", "http://127.0.0.1:5050")
    launcher_base_url: str = os.getenv("LAUNCHER_BASE_URL", "http://127.0.0.1:7000")
    camera_index: int = _int("CAMERA_INDEX", 0)
    ear_threshold: float = _float("EAR_THRESHOLD", 0.21)
    drowsy_seconds: float = _float("DROWSY_SECONDS", 2.0)
    recovery_seconds: float = _float("RECOVERY_SECONDS", 0.5)
    relay_pin: int = _int("RELAY_PIN", 17)
    buzzer_pin: int = _int("BUZZER_PIN", 18)


settings = Settings()

