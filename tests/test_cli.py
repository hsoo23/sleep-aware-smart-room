import json
from types import SimpleNamespace

import pytest

from sleep_aware.adapters import MockActionExecutor, RaspberryPiHttpActionExecutor
from sleep_aware.cli import _build_executor, _close_pipeline, main
from sleep_aware.control import Action
from sleep_aware.pipeline import ActionResult


@pytest.mark.parametrize(
    ("intention", "expected_actions"),
    [
        ("sleep", {"pause_media", "light_off", "start_session", "end_session"}),
        ("wake", {"pause_media", "light_on", "buzzer_alert", "play_media"}),
    ],
)
def test_cli_mock_run_is_deterministic_and_exercises_closed_loop(
    tmp_path, capsys, intention, expected_actions
):
    assert main(["--input", "mock", "--intention", intention, "--log-dir", str(tmp_path)]) == 0

    log_path = tmp_path / capsys.readouterr().out.strip().split("/")[-1]
    records = [json.loads(line) for line in log_path.read_text().splitlines()]
    frames = [record for record in records if record["record_type"] == "frame"]

    states = [record["state"] for record in frames]
    assert "AWAKE" in states
    assert "EYES_CLOSED" in states
    assert "DROWSY" in states
    assert states.index("AWAKE") < states.index("EYES_CLOSED") < states.index("DROWSY")
    assert states[-1] == "AWAKE"
    actions = {action["action"] for record in frames for action in record["actions"]}
    assert actions == expected_actions
    assert records[0]["record_type"] == "run_start"
    assert records[-1]["record_type"] == "run_end"
    assert records[-1]["status"] == "completed"


def test_cli_rejects_real_actions_for_mock_input(tmp_path, capsys):
    assert main(["--input", "mock", "--actions", "real", "--log-dir", str(tmp_path)]) == 1
    assert "mock 입력" in capsys.readouterr().out


def test_cli_camera_start_up_failure_is_recorded_in_run_end(tmp_path, capsys, monkeypatch):
    def fail_to_open(**kwargs):
        raise RuntimeError("camera permission denied")

    monkeypatch.setattr("sleep_aware.cli.OpenCVCameraSource", fail_to_open)

    exit_code = main(
        ["--input", "camera", "--actions", "mock", "--no-display", "--log-dir", str(tmp_path)]
    )

    assert exit_code == 1
    assert "camera permission denied" in capsys.readouterr().out
    (log_path,) = tmp_path.glob("*.jsonl")
    records = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert [record["record_type"] for record in records] == ["run_start", "run_end"]
    assert records[-1]["status"] == "failed"
    assert records[-1]["error_type"] == "RuntimeError"


def test_cli_reports_cleanup_failure_even_when_interrupted():
    class Pipeline:
        closed = False

        def close(self):
            self.closed = True

    class Policy:
        has_pending_cleanup = True

    pipeline = Pipeline()
    with pytest.raises(RuntimeError, match="종료 정리") as raised:
        try:
            raise KeyboardInterrupt
        finally:
            _close_pipeline(pipeline, Policy())

    assert pipeline.closed
    assert isinstance(raised.value.__context__, KeyboardInterrupt)


def test_cli_records_executor_close_failure_in_run_end(tmp_path, capsys, monkeypatch):
    class FailingCloseExecutor:
        def __init__(self, **kwargs):
            pass

        def execute(self, action):
            raise AssertionError("no frames are processed")

        def close(self):
            raise OSError("session close failed")

    class EmptyCamera:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def read(self):
            return None

    class Processor(EmptyCamera):
        def process(self, frame):
            return None

    monkeypatch.setattr("sleep_aware.cli.RaspberryPiHttpActionExecutor", FailingCloseExecutor)
    monkeypatch.setattr("sleep_aware.cli.OpenCVCameraSource", EmptyCamera)
    monkeypatch.setattr("sleep_aware.cli.MediaPipeFaceMeshProcessor", Processor)

    exit_code = main(
        ["--input", "camera", "--actions", "real", "--no-display", "--log-dir", str(tmp_path)]
    )

    assert exit_code == 1
    assert "session close failed" in capsys.readouterr().out
    (log_path,) = tmp_path.glob("*.jsonl")
    end = json.loads(log_path.read_text().splitlines()[-1])
    assert (end["record_type"], end["status"]) == ("run_end", "failed")
    assert end["error_type"] == "OSError"


def test_cli_keeps_cleanup_error_primary_when_executor_close_also_fails(
    tmp_path, capsys, monkeypatch
):
    class FailingCloseExecutor:
        def __init__(self, **kwargs):
            pass

        def close(self):
            raise OSError("session close failed")

    class EmptyCamera:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def read(self):
            return None

        def process(self, frame):
            return None

    def fail_cleanup(pipeline, policy):
        raise RuntimeError("종료 정리 동작이 완료되지 않았습니다")

    monkeypatch.setattr("sleep_aware.cli.RaspberryPiHttpActionExecutor", FailingCloseExecutor)
    monkeypatch.setattr("sleep_aware.cli.OpenCVCameraSource", EmptyCamera)
    monkeypatch.setattr("sleep_aware.cli.MediaPipeFaceMeshProcessor", EmptyCamera)
    monkeypatch.setattr("sleep_aware.cli._close_pipeline", fail_cleanup)

    exit_code = main(
        ["--input", "camera", "--actions", "real", "--no-display", "--log-dir", str(tmp_path)]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "종료 정리 동작이 완료되지 않았습니다" in output
    assert "session close failed" in output
    (log_path,) = tmp_path.glob("*.jsonl")
    end = json.loads(log_path.read_text().splitlines()[-1])
    assert (end["status"], end["error_type"]) == ("failed", "RuntimeError")


def _args(**overrides):
    defaults = {
        "actions": "mock",
        "allow_insecure_http": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_mock_actions_use_the_in_memory_executor():
    assert isinstance(_build_executor(_args(actions="mock")), MockActionExecutor)


def test_real_actions_send_every_action_over_http():
    executor = _build_executor(_args(actions="real"))

    assert isinstance(executor, RaspberryPiHttpActionExecutor)
    executor.close()


def test_host_actions_keep_media_on_this_host_and_devices_on_the_pi(monkeypatch):
    class RecordingBackend:
        def __init__(self, name, **kwargs):
            self.name = name
            self.actions = []

        def execute(self, action):
            self.actions.append(action)
            return ActionResult(action=action, succeeded=True)

        def close(self):
            pass

    media = RecordingBackend("media")
    http = RecordingBackend("http")
    monkeypatch.setattr("sleep_aware.cli.MacOSChromeMediaActionExecutor", lambda **kw: media)
    monkeypatch.setattr("sleep_aware.cli.RaspberryPiHttpActionExecutor", lambda **kw: http)

    executor = _build_executor(_args(actions="host"))
    for action in Action:
        assert executor.execute(action).succeeded

    assert media.actions == [Action.PAUSE_MEDIA, Action.PLAY_MEDIA]
    assert http.actions == [Action.LIGHT_OFF, Action.LIGHT_ON, Action.BUZZER_ALERT]


def test_host_actions_report_unsupported_platform_for_media_off_macos(monkeypatch):
    monkeypatch.setattr("sleep_aware.adapters.device_control.platform.system", lambda: "Linux")

    executor = _build_executor(_args(actions="host"))
    try:
        result = executor.execute(Action.PAUSE_MEDIA)
    finally:
        executor.close()

    assert not result.succeeded
    assert result.error_reason == "unsupported_platform"


def test_host_actions_track_sleep_sessions_locally():
    executor = _build_executor(_args(actions="host"))
    try:
        assert executor.execute(Action.START_SESSION).succeeded
        assert executor.execute(Action.END_SESSION).succeeded
    finally:
        executor.close()
