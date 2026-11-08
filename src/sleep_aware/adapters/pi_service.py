"""Raspberry Pi action service: the documented endpoints backed by real GPIO.

This is the physical counterpart of ``pi_stub_server``. The lamp and buzzer go through
:class:`~sleep_aware.adapters.device_control.RaspberryPiGpioActionExecutor`; sessions are
tracked in memory. Nothing on the Raspberry Pi plays media, so the media endpoints only
acknowledge the request with ``physical: false``; physical media control needs
``--actions host``. They cannot answer an error: the policy retries a failed ``play_media``
on every frame and the run then ends as failed, which would also distort RQ3 latency.

Tests inject a fake GPIO, so a passing test does not prove relay or buzzer behavior.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import threading
import time
from collections.abc import Callable, Sequence
from http.server import BaseHTTPRequestHandler
from typing import Any

from sleep_aware.adapters.device_control import (
    CompositeActionExecutor,
    RaspberryPiGpioActionExecutor,
    SessionActionExecutor,
)
from sleep_aware.adapters.pi_stub_server import (
    LOOPBACK_HOST,
    SERVED_ENDPOINTS,
    _QuietThreadingHTTPServer,
)
from sleep_aware.config import settings
from sleep_aware.control import Action

logger = logging.getLogger(__name__)

MEDIA_ACTIONS = frozenset({Action.PAUSE_MEDIA, Action.PLAY_MEDIA})
DEFAULT_ALERT_PATTERN: Sequence[float] = (0.25,) * 10
PI5_HINT = (
    "RPi.GPIO does not work on Raspberry Pi 5. "
    "Replace it with rpi-lgpio: pip uninstall RPi.GPIO && pip install rpi-lgpio."
)


class PiActionService:
    """Serve the action endpoints from GPIO and release the pins safely on close."""

    def __init__(
        self,
        *,
        gpio: Any,
        host: str = LOOPBACK_HOST,
        port: int = 5050,
        relay_pin: int = 17,
        buzzer_pin: int = 18,
        alert_pattern: Sequence[float] = DEFAULT_ALERT_PATTERN,
        buzzer_dedupe_seconds: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if buzzer_dedupe_seconds < 0:
            raise ValueError("buzzer_dedupe_seconds must not be negative")
        self._buzzer_dedupe_seconds = buzzer_dedupe_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._last_alert_at: float | None = None
        self._alert_thread: threading.Thread | None = None
        self._serve_thread: threading.Thread | None = None
        # Bind first: a port conflict must not leave the pins configured.
        self._server = _QuietThreadingHTTPServer((host, port), self._handler_class())
        try:
            self._gpio = RaspberryPiGpioActionExecutor(
                gpio=gpio,
                relay_pin=relay_pin,
                buzzer_pin=buzzer_pin,
                alert_pattern=alert_pattern,
            )
        except Exception:
            self._server.server_close()
            raise
        session = SessionActionExecutor()
        self._backend = CompositeActionExecutor(
            {
                Action.PAUSE_MEDIA: session,
                Action.PLAY_MEDIA: session,
                Action.LIGHT_OFF: self._gpio,
                Action.LIGHT_ON: self._gpio,
                Action.BUZZER_ALERT: self._gpio,
                Action.START_SESSION: session,
                Action.END_SESSION: session,
            }
        )

    @property
    def port(self) -> int:
        """Bound port; useful when the service was started on port ``0``."""
        return self._server.server_address[1]

    def start(self) -> PiActionService:
        """Turn the lamp on as the legacy service did, then serve in the background."""
        if self._serve_thread is not None:
            raise RuntimeError("service is already running")
        initial = self._gpio.execute(Action.LIGHT_ON)
        if not initial.succeeded:
            raise RuntimeError(f"Could not set initial lamp state: {initial.error_reason}")
        self._serve_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._serve_thread.start()
        return self

    def close(self) -> None:
        """Stop serving, let a running alert finish, then release GPIO."""
        if self._serve_thread is not None:
            self._server.shutdown()
            self._serve_thread.join(timeout=5)
            self._serve_thread = None
        self._server.server_close()
        with self._lock:
            alert_thread = self._alert_thread
        if alert_thread is not None:
            alert_thread.join()
        self._backend.close()

    def __enter__(self) -> PiActionService:
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.close()

    def _handle(self, path: str) -> tuple[int, dict[str, Any]]:
        action = SERVED_ENDPOINTS.get(path)
        if action is None:
            return 404, {"error": "unknown endpoint"}
        if action in MEDIA_ACTIONS:
            logger.warning("media_not_connected action=%s", action.value)
            return 200, {"action": action.value, "succeeded": True, "physical": False}
        if action is Action.BUZZER_ALERT:
            return self._start_alert()
        with self._lock:
            result = self._backend.execute(action)
        if result.succeeded:
            return 200, {"action": action.value, "succeeded": True}
        return 500, {
            "action": action.value,
            "succeeded": False,
            "error_reason": result.error_reason,
        }

    def _start_alert(self) -> tuple[int, dict[str, Any]]:
        """Start the buzzer without blocking the response.

        The default pattern lasts 2.5 s, longer than the 2 s client timeout, and waiting
        for it would also stall the detection loop that sent the request.
        """
        now = self._clock()
        with self._lock:
            if self._alert_thread is not None and self._alert_thread.is_alive():
                duplicate = True
            else:
                duplicate = (
                    self._last_alert_at is not None
                    and now - self._last_alert_at < self._buzzer_dedupe_seconds
                )
            if duplicate:
                return 200, {
                    "action": Action.BUZZER_ALERT.value,
                    "succeeded": True,
                    "deduplicated": True,
                }
            self._last_alert_at = now
            self._alert_thread = threading.Thread(target=self._run_alert, daemon=True)
            self._alert_thread.start()
        return 202, {"action": Action.BUZZER_ALERT.value, "succeeded": True}

    def _run_alert(self) -> None:
        result = self._gpio.execute(Action.BUZZER_ALERT)
        if not result.succeeded:
            # The 202 has already been sent, so this log is the only failure record.
            logger.error("buzzer_alert_failed error_reason=%s", result.error_reason)

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        service = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler.
                status, payload = service._handle(self.path)
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler.
                # State-changing endpoints are POST only, matching the documented contract.
                self.send_error(405, "use POST")

            def log_message(self, *_: Any) -> None:
                """Stay quiet; client addresses are not part of the experiment record."""

        return Handler


def _raise_interrupt(*_: object) -> None:
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--host",
        default=LOOPBACK_HOST,
        help="Bind address; defaults to loopback for access through an SSH tunnel",
    )
    parser.add_argument("--port", type=int, default=5050)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    # systemctl stop and kill send SIGTERM and a dropped SSH session sends SIGHUP; all of
    # them must still reach GPIO cleanup.
    signal.signal(signal.SIGTERM, _raise_interrupt)
    signal.signal(signal.SIGHUP, _raise_interrupt)

    try:
        import RPi.GPIO as GPIO  # noqa: N814 - the conventional name of this module.
    except (ImportError, RuntimeError) as error:
        print(f"Run failed: could not import RPi.GPIO: {error}")
        print("On Raspberry Pi, install with pip install -e '.[raspberrypi]'.")
        return 1

    service: PiActionService | None = None
    try:
        service = PiActionService(
            gpio=GPIO,
            host=args.host,
            port=args.port,
            relay_pin=settings.relay_pin,
            buzzer_pin=settings.buzzer_pin,
        )
        service.start()
        print(f"{args.host}:{service.port} (Ctrl+C to stop)")
        threading.Event().wait()
    except KeyboardInterrupt:
        print("Stopped.")
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Run failed: {error}")
        if "SOC peripheral" in str(error):
            print(PI5_HINT)
        if service is not None:
            _close_reporting(service)
        return 1
    if service is not None and not _close_reporting(service):
        return 1
    return 0


def _close_reporting(service: PiActionService) -> bool:
    """Close the service and report a failed GPIO release instead of hiding it."""
    try:
        service.close()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"GPIO cleanup failed: {error}. Check the relay and buzzer state.")
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
