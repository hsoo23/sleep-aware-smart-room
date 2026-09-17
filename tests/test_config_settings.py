"""Configuration loading checks.

``sleep_aware.config`` reads the environment at import time, so each case loads it in a
fresh interpreter with a controlled environment instead of reloading modules in-process.
"""

import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sleep_aware.config import Settings, settings

ROOT = Path(__file__).resolve().parents[1]
SETTING_ENV_NAMES = {field.name.upper() for field in dataclasses.fields(Settings)}

_LOAD_SETTINGS = (
    "import dataclasses, json; from sleep_aware.config import settings; "
    "print(json.dumps(dataclasses.asdict(settings)))"
)


def _run_config(env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key not in SETTING_ENV_NAMES}
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT / "src"), env.get("PYTHONPATH")]))
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", _LOAD_SETTINGS],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )


def _load_settings(env_overrides: dict[str, str]) -> dict:
    completed = _run_config(env_overrides)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def _env_example_keys() -> set[str]:
    keys = set()
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            keys.add(stripped.split("=", 1)[0].strip())
    return keys


def test_config_fixed_ear_baseline_defaults_without_environment():
    loaded = _load_settings({})

    assert loaded["ear_threshold"] == pytest.approx(0.21)
    assert loaded["drowsy_seconds"] == pytest.approx(2.0)
    assert loaded["recovery_seconds"] == pytest.approx(0.5)
    assert loaded["camera_index"] == 0


def test_config_environment_overrides_typed_values():
    loaded = _load_settings(
        {
            "EAR_THRESHOLD": "0.25",
            "DROWSY_SECONDS": "3",
            "CAMERA_INDEX": "2",
            "PI_BASE_URL": "http://pi.local:5050",
        }
    )

    assert loaded["ear_threshold"] == pytest.approx(0.25)
    assert loaded["drowsy_seconds"] == pytest.approx(3.0)
    assert loaded["camera_index"] == 2
    assert loaded["pi_base_url"] == "http://pi.local:5050"


@pytest.mark.parametrize(
    ("name", "value"),
    [("EAR_THRESHOLD", "not-a-number"), ("CAMERA_INDEX", "1.5"), ("RELAY_PIN", "")],
)
def test_config_invalid_numeric_environment_value_fails_at_import(name, value):
    completed = _run_config({name: value})

    assert completed.returncode != 0
    assert "ValueError" in completed.stderr


def test_config_settings_are_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.ear_threshold = 0.5  # type: ignore[misc]


def test_config_every_setting_is_documented_in_env_example():
    missing = SETTING_ENV_NAMES - _env_example_keys()

    assert not missing, f".env.example is missing: {sorted(missing)}"
