import json

import pytest

from sleep_aware.cli import main


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
