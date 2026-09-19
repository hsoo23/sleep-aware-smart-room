"""RQ1 evidence: repeated mock runs must produce the same decisions and actions."""

from __future__ import annotations

import json
from dataclasses import replace

from sleep_aware.config import settings
from sleep_aware.control import Intention
from sleep_aware.eventlog import mock_run

RUNS = 3
# Values that legitimately differ between runs and are excluded from the comparison.
VOLATILE_FIELDS = frozenset({"run_id", "wall_time_utc", "git_dirty"})


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _fingerprint(records):
    start, *frames, end = records
    return {
        "detector_config": start["detector_config"],
        "intention": start["intention"],
        "states": [(frame["previous_state"], frame["state"]) for frame in frames],
        "actions": [
            (action["action"], action["success"], action["failure_reason"])
            for frame in frames
            for action in frame["actions"]
        ],
        "status": end["status"],
        "frame_count": end["frame_count"],
    }


def _run_many(tmp_path, intention):
    fingerprints = []
    for index in range(RUNS):
        path = mock_run.run_mock(tmp_path / f"run-{index}", intention)
        fingerprints.append(_fingerprint(_records(path)))
    return fingerprints


def test_repeated_mock_runs_are_identical(tmp_path, monkeypatch):
    # The scenario must not depend on the local detector environment.
    monkeypatch.setattr(mock_run, "settings", replace(settings, drowsy_seconds=10.0))

    for intention in Intention:
        first, *rest = _run_many(tmp_path / intention.value, intention)

        assert first["states"], f"{intention.value}: no frames were recorded"
        for other in rest:
            assert other == first, f"{intention.value}: repeated run differed"


def test_repeated_runs_still_get_unique_run_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(mock_run, "settings", replace(settings, drowsy_seconds=10.0))

    run_ids = set()
    for index in range(RUNS):
        path = mock_run.run_mock(tmp_path / f"run-{index}", Intention.WAKE)
        start = _records(path)[0]
        run_ids.add(start["run_id"])
        assert VOLATILE_FIELDS <= set(start)

    assert len(run_ids) == RUNS
