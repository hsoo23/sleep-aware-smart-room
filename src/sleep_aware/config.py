"""Environment-backed configuration shared by host and Raspberry Pi services."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _float(name: str, default: float) -> float:
    """Read one floating-point setting from the environment."""
    return float(os.getenv(name, default))


def _int(name: str, default: int) -> int:
    """Read one integer setting from the environment."""
    return int(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    pi_base_url: str = os.getenv("PI_BASE_URL", "http://127.0.0.1:5050")
    pi_timeout_seconds: float = _float("PI_TIMEOUT_SECONDS", 2.0)
    launcher_base_url: str = os.getenv("LAUNCHER_BASE_URL", "http://127.0.0.1:7000")
    camera_index: int = _int("CAMERA_INDEX", 0)
    camera_width: int = _int("CAMERA_WIDTH", 640)
    camera_height: int = _int("CAMERA_HEIGHT", 480)
    ear_threshold: float = _float("EAR_THRESHOLD", 0.21)
    drowsy_seconds: float = _float("DROWSY_SECONDS", 2.0)
    recovery_seconds: float = _float("RECOVERY_SECONDS", 0.5)
    face_landmarker_model: str = os.getenv(
        "FACE_LANDMARKER_MODEL", "models/face_landmarker.task"
    )
    face_mesh_max_num_faces: int = _int("FACE_MESH_MAX_NUM_FACES", 1)
    face_mesh_refine_landmarks: bool = os.getenv(
        "FACE_MESH_REFINE_LANDMARKS", "true"
    ).lower() in {"1", "true", "yes", "on"}
    face_mesh_min_detection_confidence: float = _float(
        "FACE_MESH_MIN_DETECTION_CONFIDENCE", 0.5
    )
    face_mesh_min_tracking_confidence: float = _float(
        "FACE_MESH_MIN_TRACKING_CONFIDENCE", 0.5
    )
    relay_pin: int = _int("RELAY_PIN", 17)
    buzzer_pin: int = _int("BUZZER_PIN", 18)
    log_dir: str = os.getenv("LOG_DIR", "results/logs")


settings = Settings()
