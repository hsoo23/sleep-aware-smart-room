from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sleep_aware.config import settings
from sleep_aware.control import Action, Intention
from sleep_aware.detection import DrowsinessState
from sleep_aware.eventlog import (
    SCHEMA_VERSION,
    JsonlEventLogger,
    RunMetadata,
    mock_run,
    new_run_id,
    redact,
    validate_record,
)
from sleep_aware.eventlog.schema import ACTION_FIELDS, RECORD_FIELDS
from sleep_aware.pipeline import ActionResult, LatencyBreakdown, PipelineEvent

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = datetime(2026, 9, 15, 1, 2, 3, tzinfo=timezone.utc)


def _metadata(run_id: str = "20260915T010203Z-00000000") -> RunMetadata:
    return RunMetadata(
        run_id=run_id,
        intention=Intention.WAKE,
        detector_name="B0-fixed-ear",
        detector_version="0.1.0",
        config_version="test",
        detector_config={"ear_threshold": 0.21},
        git_commit="0" * 40,
        git_dirty=False,
    )


def _event(detail: str | None = "device unavailable") -> PipelineEvent:
    return PipelineEvent(
        frame_sequence=3,
        timestamp=12.5,
        intention=Intention.WAKE,
        ear=0.15,
        ear_threshold=0.21,
        previous_state=DrowsinessState.EYES_CLOSED,
        state=DrowsinessState.DROWSY,
        actions=(Action.PAUSE_MEDIA, Action.LIGHT_ON),
        action_results=(
            ActionResult(Action.PAUSE_MEDIA, succeeded=True, latency=0.01),
            ActionResult(Action.LIGHT_ON, succeeded=False, detail=detail, latency=0.02),
        ),
        latency=LatencyBreakdown(inference=0.0125, control=0.03, end_to_end=0.0425),
    )


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_logger_writes_valid_run_start_frame_and_run_end(tmp_path):
    with JsonlEventLogger(tmp_path, _metadata(), wall_clock=lambda: FIXED_NOW) as logger:
        logger.log(_event())

    assert logger.path == tmp_path / "20260915T010203Z-00000000.jsonl"
    start, frame, end = _read(logger.path)
    for record in (start, frame, end):
        validate_record(record)
        assert record["schema_version"] == SCHEMA_VERSION
        assert record["run_id"] == "20260915T010203Z-00000000"
        assert record["wall_time_utc"] == "2026-09-15T01:02:03+00:00"

    assert start["git_commit"] == "0" * 40
    assert start["detector_config"] == {"ear_threshold": 0.21}
    assert frame["frame_sequence"] == 3
    assert frame["monotonic_timestamp_s"] == 12.5
    assert frame["state_changed"] is True
    assert frame["actions"] == [
        {"action": "pause_media", "success": True, "failure_reason": None, "latency_ms": 10.0},
        {
            "action": "light_on",
            "success": False,
            "failure_reason": "device unavailable",
            "latency_ms": 20.0,
        },
    ]
    assert frame["inference_latency_ms"] == 12.5
    assert frame["control_latency_ms"] == 30.0
    assert frame["end_to_end_latency_ms"] == 42.5
    assert (end["status"], end["frame_count"], end["error_type"]) == ("completed", 1, None)


def test_logger_records_failed_run_and_refuses_to_overwrite(tmp_path):
    with pytest.raises(RuntimeError), JsonlEventLogger(tmp_path, _metadata()) as logger:
        raise RuntimeError("camera lost")

    end = _read(logger.path)[-1]
    assert end["status"] == "failed"
    assert end["error_type"] == "RuntimeError"
    with pytest.raises(FileExistsError):
        JsonlEventLogger(tmp_path, _metadata())


def test_logger_redacts_personal_and_network_identifiers(tmp_path):
    detail = (
        "POST http://192.168.0.17:5050/light failed for someone@example.com "
        "via 10.0.0.2:22 and fe80::1ff:fe23:4567:890a from /Users/someone/project"
    )
    with JsonlEventLogger(tmp_path, _metadata()) as logger:
        logger.log(_event(detail))

    text = logger.path.read_text(encoding="utf-8")
    for secret in ("192.168", "someone", "10.0.0.2", "fe80", "5050"):
        assert secret not in text
    reason = _read(logger.path)[1]["actions"][1]["failure_reason"]
    assert reason == "POST <url> failed for <email> via <ip> and <ip> from <path>"


def test_redact_removes_whole_url_containing_credentials_path_and_query():
    assert redact("GET https://user@example.com/private?token=secret failed") == (
        "GET <url> failed"
    )


def test_logger_removes_file_when_run_start_cannot_be_written(tmp_path):
    def broken_clock():
        raise RuntimeError("clock unavailable")

    with pytest.raises(RuntimeError):
        JsonlEventLogger(tmp_path, _metadata(), wall_clock=broken_clock)

    assert list(tmp_path.iterdir()) == []
    with JsonlEventLogger(tmp_path, _metadata()) as logger:
        pass
    assert logger.path.exists()


def test_redact_keeps_ordinary_failure_text():
    assert redact("relay timeout after 12:30:45 (attempt 2/3)") == (
        "relay timeout after 12:30:45 (attempt 2/3)"
    )


@pytest.mark.parametrize("record_type", sorted(RECORD_FIELDS))
def test_schema_rejects_missing_fields(record_type):
    record = {"schema_version": SCHEMA_VERSION, "record_type": record_type}

    with pytest.raises(ValueError, match="missing field 'run_id'"):
        validate_record(record)


def test_schema_rejects_wrong_types_enums_and_negative_latency(tmp_path):
    with JsonlEventLogger(tmp_path, _metadata()) as logger:
        logger.log(_event())
    frame = _read(logger.path)[1]

    invalid = {
        **frame,
        "frame_sequence": "3",
        "state_changed": 1,
        "state": "SLEEPING",
        "end_to_end_latency_ms": -1.0,
        "actions": [{**frame["actions"][0], "success": "yes"}],
        "extra": True,
    }
    with pytest.raises(ValueError) as error:
        validate_record(invalid)

    message = str(error.value)
    assert "'frame_sequence' must be int" in message
    assert "'state_changed' must be bool" in message
    assert "unknown value 'SLEEPING'" in message
    assert "'end_to_end_latency_ms' must be non-negative" in message
    assert "frame.actions[0]: field 'success' must be bool" in message
    assert "unexpected field 'extra'" in message
    for value in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="'ear' must be finite"):
            validate_record({**frame, "ear": value})
    with pytest.raises(ValueError, match="unknown record_type"):
        validate_record({"record_type": "debug"})


def test_mock_pipeline_run_produces_valid_log(tmp_path, monkeypatch):
    # The mock scenario must not depend on the local detector environment.
    monkeypatch.setattr(mock_run, "settings", replace(settings, drowsy_seconds=10.0))
    path = mock_run.run_mock(tmp_path, Intention.WAKE)

    records = _read(path)
    for record in records:
        validate_record(record)
    start, *frames, end = records
    assert start["record_type"] == "run_start"
    assert end["record_type"] == "run_end"
    assert end["frame_count"] == len(frames) > 0
    assert [frame["frame_sequence"] for frame in frames] == list(range(len(frames)))
    assert {frame["run_id"] for frame in frames} == {start["run_id"]}

    transitions = [
        (frame["previous_state"], frame["state"]) for frame in frames if frame["state_changed"]
    ]
    assert ("EYES_CLOSED", "DROWSY") in transitions
    assert ("DROWSY", "AWAKE") in transitions
    assert ("AWAKE", "NO_FACE") in transitions

    actions = [action for frame in frames for action in frame["actions"]]
    assert (actions[1]["action"], actions[1]["success"]) == ("light_on", False)
    assert actions[1]["failure_reason"] == "simulated device timeout"
    for frame in frames:
        assert frame["end_to_end_latency_ms"] >= frame["inference_latency_ms"]
        assert frame["end_to_end_latency_ms"] >= frame["control_latency_ms"]


def test_run_ids_are_sortable_and_unique():
    first, second = new_run_id(FIXED_NOW), new_run_id(FIXED_NOW)

    assert re.fullmatch(r"20260915T010203Z-[0-9a-f]{8}", first)
    assert first != second


def test_action_schema_matches_logger_output(tmp_path):
    with JsonlEventLogger(tmp_path, _metadata()) as logger:
        logger.log(_event())

    for action in _read(logger.path)[1]["actions"]:
        assert set(action) == set(ACTION_FIELDS)


def test_schema_rejects_sensitive_or_unknown_detector_config():
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "run_start",
        "run_id": "run",
        "wall_time_utc": FIXED_NOW.isoformat(),
        "intention": "wake",
        "software_version": "0.1.0",
        "git_commit": None,
        "git_dirty": None,
        "detector_name": "fixed-ear",
        "detector_version": "1",
        "config_version": "test",
        "detector_config": {"device_url": "http://192.168.0.2"},
        "python_version": "3.10",
        "platform": "test",
    }

    with pytest.raises(ValueError, match="detector_config"):
        validate_record(record)


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_default_log_directory_is_ignored_by_git():
    result = subprocess.run(
        ["git", "check-ignore", "-q", "results/logs/20260915T010203Z-00000000.jsonl"],
        cwd=REPO_ROOT,
        check=False,
    )

    if result.returncode == 128:
        pytest.skip("not running inside a Git checkout")
    assert result.returncode == 0
