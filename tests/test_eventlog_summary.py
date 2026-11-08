"""Run-log summary checks against logs written by the real mock run."""

from __future__ import annotations

import json

import pytest

from sleep_aware.control import Action, Intention
from sleep_aware.eventlog.mock_run import run_mock
from sleep_aware.eventlog.summary import _stats, format_summary, main, summarize


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def wake_log(tmp_path):
    return run_mock(tmp_path, Intention.WAKE, failing_action=None)


def test_stats_use_the_median_and_nearest_rank_p95():
    stats = _stats([float(value) for value in range(1, 101)])

    assert (stats.count, stats.median_ms, stats.p95_ms) == (100, 50.5, 95.0)
    assert _stats([7.0]).p95_ms == 7.0
    assert _stats([]) is None


def test_summary_reports_the_run_and_separates_action_frames(wake_log):
    records = _records(wake_log)
    frames = [record for record in records if record["record_type"] == "frame"]

    summary = summarize(records)

    assert summary.status == "completed"
    assert summary.frame_count == len(frames)
    assert summary.fps > 0
    assert summary.control.count == len(frames)
    assert summary.control_with_actions.count == sum(1 for frame in frames if frame["actions"])
    assert summary.control_with_actions.count < summary.control.count
    assert [name for name, _, _ in summary.actions] == [
        "pause_media",
        "light_on",
        "buzzer_alert",
        "play_media",
    ]
    assert summary.states[:3] == ("AWAKE", "EYES_CLOSED", "DROWSY")


def test_log_without_run_end_is_reported_as_interrupted(wake_log):
    records = [record for record in _records(wake_log) if record["record_type"] != "run_end"]

    assert summarize(records).status == "interrupted"


def test_action_failures_keep_their_reason(tmp_path):
    log = run_mock(tmp_path, Intention.WAKE, failing_action=Action.BUZZER_ALERT)

    text = format_summary(summarize(_records(log)))

    assert "buzzer_alert: failure" in text


def test_invalid_log_fails_without_a_traceback(tmp_path, capsys):
    broken = tmp_path / "broken.jsonl"
    broken.write_text('{"record_type": "frame"}\n', encoding="utf-8")

    assert main([str(broken)]) == 1
    assert "Summary failed" in capsys.readouterr().out
    assert main([str(tmp_path / "missing.jsonl")]) == 1


def test_main_prints_the_summary(wake_log, capsys):
    assert main([str(wake_log)]) == 0
    assert "control (action frames)" in capsys.readouterr().out
