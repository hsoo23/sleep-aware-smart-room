"""Run-level metadata recorded once at the start of every log."""

from __future__ import annotations

import platform as _platform
import secrets
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sleep_aware import __version__
from sleep_aware.control import Intention

ConfigValue = str | int | float | bool | None


@dataclass(frozen=True)
class RunMetadata:
    """Reproducibility context for one run.

    ``detector_config`` must contain only experimental parameters (for example
    thresholds and durations), never URLs, credentials, or device addresses.
    """

    run_id: str
    intention: Intention
    detector_name: str
    detector_version: str
    config_version: str
    detector_config: Mapping[str, ConfigValue] = field(default_factory=dict)
    software_version: str = __version__
    git_commit: str | None = None
    git_dirty: bool | None = None
    python_version: str = _platform.python_version()
    platform: str = f"{_platform.system()}-{_platform.machine()}"


def new_run_id(now: datetime | None = None) -> str:
    """Return a sortable, collision-resistant run ID such as ``20260915T010203Z-1a2b3c4d``."""
    now = now or datetime.now(timezone.utc)
    return f"{now.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"


def _git(args: list[str], cwd: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=5, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def git_revision(cwd: Path | str = ".") -> tuple[str | None, bool | None]:
    """Return ``(commit, dirty)`` for tracked files, or ``(None, None)`` outside Git."""
    cwd = Path(cwd)
    commit = _git(["rev-parse", "HEAD"], cwd)
    if not commit:
        return None, None
    status = _git(["status", "--porcelain", "--untracked-files=no"], cwd)
    return commit, (bool(status) if status is not None else None)
