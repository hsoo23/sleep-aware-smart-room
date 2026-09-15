"""Guard that the core package imports on a runner without camera or GPIO packages."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CORE_MODULES = [
    "sleep_aware",
    "sleep_aware.config",
    "sleep_aware.detection",
    "sleep_aware.control",
    "sleep_aware.pipeline",
]
HARDWARE_MODULES = ["cv2", "mediapipe", "RPi", "pyautogui", "flask"]

_CHECK_IMPORTS = """
import importlib, json, sys
for name in {core!r}:
    importlib.import_module(name)
print(json.dumps(sorted(name for name in {hardware!r} if name in sys.modules)))
"""


def test_core_modules_import_without_hardware_dependencies():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT / "src"), env.get("PYTHONPATH")]))
    script = _CHECK_IMPORTS.format(core=CORE_MODULES, hardware=HARDWARE_MODULES)

    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == [], "core import pulled in hardware-only packages"
