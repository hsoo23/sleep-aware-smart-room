from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest
import requests

from sleep_aware.adapters import (
    ACTION_ENDPOINTS,
    DeviceState,
    MockActionExecutor,
    RaspberryPiHttpActionExecutor,
)
from sleep_aware.control import Action


@dataclass
class StubResponse:
    status_code: int = 204
    text: str = ""
    closed: bool = False

    def close(self) -> None:
        self.closed = True


class StubTransport:
    def __init__(self, outcome: StubResponse | Exception) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, str, float, bool, bool]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        timeout: float,
        allow_redirects: bool,
        stream: bool,
    ) -> StubResponse:
        self.calls.append((method, url, timeout, allow_redirects, stream))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def ticking_clock(*values: float):
    times = iter(values)
    return lambda: next(times)


def test_mock_executor_exposes_all_device_states_and_safe_repeated_commands():
    executor = MockActionExecutor()

    for action in (
        Action.PAUSE_MEDIA,
        Action.LIGHT_OFF,
        Action.START_SESSION,
        Action.PAUSE_MEDIA,
        Action.LIGHT_OFF,
        Action.START_SESSION,
        Action.BUZZER_ALERT,
    ):
        result = executor.execute(action)
        assert result.succeeded
        assert result.elapsed_ms == 0.0

    assert executor.state == DeviceState(
        light_on=False,
        buzzer_alert_count=1,
        media_playing=False,
        session_active=True,
    )

    executor.execute(Action.PLAY_MEDIA)
    executor.execute(Action.LIGHT_ON)
    executor.execute(Action.END_SESSION)

    assert executor.state.media_playing
    assert executor.state.light_on
    assert not executor.state.session_active


@pytest.mark.parametrize("action", list(Action))
def test_http_executor_posts_each_action_to_its_mapped_endpoint(action: Action):
    response = StubResponse()
    transport = StubTransport(response)
    executor = RaspberryPiHttpActionExecutor(
        base_url="http://pi.invalid:5050/",
        timeout_seconds=1.25,
        transport=transport,
        clock=ticking_clock(10.0, 10.042),
        allow_insecure_http=True,
    )

    result = executor.execute(action)

    assert result.succeeded
    assert result.status_code == 204
    assert result.elapsed_ms == pytest.approx(42.0)
    assert transport.calls == [
        ("POST", f"http://pi.invalid:5050{ACTION_ENDPOINTS[action]}", 1.25, False, True)
    ]
    assert response.closed


@pytest.mark.parametrize(
    ("exception", "reason", "detail"),
    [
        (requests.Timeout(), "timeout", "request timed out"),
        (requests.ConnectionError(), "connection_error", "could not connect to device"),
        (requests.RequestException(), "request_error", "HTTP request failed"),
    ],
)
def test_http_executor_returns_and_logs_network_failures(
    exception: Exception,
    reason: str,
    detail: str,
    caplog: pytest.LogCaptureFixture,
):
    executor = RaspberryPiHttpActionExecutor(
        base_url="http://pi.invalid:5050",
        timeout_seconds=2.0,
        transport=StubTransport(exception),
        clock=ticking_clock(1.0, 1.015),
        allow_insecure_http=True,
    )

    with caplog.at_level(logging.WARNING):
        result = executor.execute(Action.LIGHT_ON)

    assert not result.succeeded
    assert result.error_reason == reason
    assert result.detail == detail
    assert result.elapsed_ms == pytest.approx(15.0)
    record = caplog.records[-1]
    assert record.message == "action_execution_failed"
    assert record.action == "light_on"
    assert record.error_reason == reason
    assert record.elapsed_ms == pytest.approx(15.0)
    assert not hasattr(record, "base_url")


def test_http_executor_returns_non_success_status_without_response_body(caplog):
    response = StubResponse(status_code=503, text="private diagnostics")
    executor = RaspberryPiHttpActionExecutor(
        base_url="http://pi.invalid:5050",
        timeout_seconds=2.0,
        transport=StubTransport(response),
        clock=ticking_clock(2.0, 2.005),
        allow_insecure_http=True,
    )

    with caplog.at_level(logging.WARNING):
        result = executor.execute(Action.START_SESSION)

    assert not result.succeeded
    assert result.status_code == 503
    assert result.error_reason == "http_status"
    assert result.detail == "device returned HTTP 503"
    assert "private diagnostics" not in caplog.text
    assert response.closed


@pytest.mark.parametrize(
    ("base_url", "timeout_seconds"),
    [("", 1.0), (" ", 1.0), ("http://pi.invalid", 0.0), ("http://pi.invalid", -1.0)],
)
def test_http_executor_rejects_invalid_configuration(base_url: str, timeout_seconds: float):
    with pytest.raises(ValueError):
        RaspberryPiHttpActionExecutor(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )


def test_http_executor_rejects_remote_plain_http_without_explicit_opt_in():
    with pytest.raises(ValueError, match="plain HTTP"):
        RaspberryPiHttpActionExecutor(
            base_url="http://192.168.0.10:5050",
            timeout_seconds=1.0,
        )


@pytest.mark.parametrize(
    "base_url",
    ["http://localhost:5050", "http://127.0.0.1:5050", "https://pi.invalid"],
)
def test_http_executor_allows_loopback_http_or_https(base_url: str):
    RaspberryPiHttpActionExecutor(base_url=base_url, timeout_seconds=1.0)
