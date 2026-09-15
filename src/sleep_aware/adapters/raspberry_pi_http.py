"""HTTP implementation of the action executor contract."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from typing import Protocol

import requests

from sleep_aware.control import Action
from sleep_aware.pipeline.models import ActionResult


ACTION_ENDPOINTS: Mapping[Action, str] = {
    Action.PAUSE_MEDIA: "/actions/media/pause",
    Action.PLAY_MEDIA: "/actions/media/play",
    Action.LIGHT_OFF: "/actions/light/off",
    Action.LIGHT_ON: "/actions/light/on",
    Action.BUZZER_ALERT: "/actions/buzzer/alert",
    Action.START_SESSION: "/actions/session/start",
    Action.END_SESSION: "/actions/session/end",
}


class HttpResponse(Protocol):
    status_code: int

    def close(self) -> None: ...


class HttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        timeout: float,
        allow_redirects: bool,
        stream: bool,
    ) -> HttpResponse: ...


class RaspberryPiHttpActionExecutor:
    """Send state-changing actions to a Raspberry Pi over bounded HTTP calls."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        transport: HttpTransport | None = None,
        endpoints: Mapping[Action, str] = ACTION_ENDPOINTS,
        logger: logging.Logger | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        missing = set(Action) - set(endpoints)
        if missing:
            names = ", ".join(sorted(action.value for action in missing))
            raise ValueError(f"missing endpoint mappings: {names}")

        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport or requests.Session()
        self._endpoints = dict(endpoints)
        self._logger = logger or logging.getLogger(__name__)
        self._clock = clock

    def execute(self, action: Action) -> ActionResult:
        """POST one action and convert expected network failures into results."""
        started_at = self._clock()
        try:
            response = self._transport.request(
                "POST",
                f"{self._base_url}{self._endpoints[action]}",
                timeout=self._timeout_seconds,
                allow_redirects=False,
                stream=True,
            )
        except requests.Timeout:
            return self._failure(action, started_at, "timeout", "request timed out")
        except requests.ConnectionError:
            return self._failure(
                action, started_at, "connection_error", "could not connect to device"
            )
        except requests.RequestException:
            return self._failure(action, started_at, "request_error", "HTTP request failed")

        try:
            elapsed_ms = self._elapsed_ms(started_at)
            if not 200 <= response.status_code < 300:
                return self._failure(
                    action,
                    started_at,
                    "http_status",
                    f"device returned HTTP {response.status_code}",
                    status_code=response.status_code,
                    elapsed_ms=elapsed_ms,
                )
            return ActionResult(
                action=action,
                succeeded=True,
                elapsed_ms=elapsed_ms,
                status_code=response.status_code,
            )
        finally:
            response.close()

    def _elapsed_ms(self, started_at: float) -> float:
        return max(0.0, (self._clock() - started_at) * 1000.0)

    def _failure(
        self,
        action: Action,
        started_at: float,
        error_reason: str,
        detail: str,
        *,
        status_code: int | None = None,
        elapsed_ms: float | None = None,
    ) -> ActionResult:
        duration = self._elapsed_ms(started_at) if elapsed_ms is None else elapsed_ms
        self._logger.warning(
            "action_execution_failed",
            extra={
                "action": action.value,
                "error_reason": error_reason,
                "elapsed_ms": duration,
                "status_code": status_code,
            },
        )
        return ActionResult(
            action=action,
            succeeded=False,
            detail=detail,
            elapsed_ms=duration,
            error_reason=error_reason,
            status_code=status_code,
        )
