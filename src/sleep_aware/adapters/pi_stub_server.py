"""Loopback stand-in for the Raspberry Pi action service.

The stub answers the endpoints in ``docs/RASPBERRY_PI_SMOKE_TEST.md`` with the
in-memory :class:`~sleep_aware.adapters.mock_action.MockActionExecutor`, so the
``--actions real`` HTTP path can be exercised without a Raspberry Pi, a relay, or
a buzzer. It proves the request path, not physical device behavior, and binds to
the loopback interface only.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from sleep_aware.adapters.mock_action import DeviceState, MockActionExecutor
from sleep_aware.control import Action

LOOPBACK_HOST = "127.0.0.1"

# Declared independently of the client mapping so a typo on either side fails the
# integration tests instead of matching itself. See docs/RASPBERRY_PI_SMOKE_TEST.md.
SERVED_ENDPOINTS: Mapping[str, Action] = {
    "/actions/media/pause": Action.PAUSE_MEDIA,
    "/actions/media/play": Action.PLAY_MEDIA,
    "/actions/light/off": Action.LIGHT_OFF,
    "/actions/light/on": Action.LIGHT_ON,
    "/actions/buzzer/alert": Action.BUZZER_ALERT,
    "/actions/session/start": Action.START_SESSION,
    "/actions/session/end": Action.END_SESSION,
}


class _QuietThreadingHTTPServer(ThreadingHTTPServer):
    """Keep client disconnects out of the test and demonstration output."""

    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        if isinstance(sys.exc_info()[1], ConnectionResetError | BrokenPipeError):
            return
        super().handle_error(request, client_address)


class PiStubServer:
    """Serve the Raspberry Pi action endpoints from memory on the loopback interface."""

    def __init__(
        self,
        *,
        port: int = 5050,
        failing_actions: frozenset[Action] = frozenset(),
        failure_status: int = 503,
    ) -> None:
        if not 100 <= failure_status <= 599:
            raise ValueError("failure_status must be a valid HTTP status code")
        if failure_status <= 299:
            # 1xx is not a final response and 2xx is recorded as success, so neither
            # would reach the executor as the failure this rehearsal is meant to show.
            raise ValueError("failure_status must not be a 1xx or 2xx status code")
        self.executor = MockActionExecutor()
        self._failing_actions = frozenset(failing_actions)
        self._failure_status = failure_status
        self._lock = threading.Lock()
        self._server = _QuietThreadingHTTPServer((LOOPBACK_HOST, port), self._handler_class())
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        """Bound port; useful when the server was started on port ``0``."""
        return self._server.server_address[1]

    @property
    def base_url(self) -> str:
        return f"http://{LOOPBACK_HOST}:{self.port}"

    @property
    def state(self) -> DeviceState:
        return self.executor.state

    def start(self) -> PiStubServer:
        """Serve requests on a background thread."""
        if self._thread is not None:
            raise RuntimeError("server is already running")
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def close(self) -> None:
        """Stop serving and release the socket; repeated calls are ignored."""
        if self._thread is None:
            self._server.server_close()
            return
        self._server.shutdown()
        self._thread.join(timeout=5)
        self._thread = None
        self._server.server_close()

    def __enter__(self) -> PiStubServer:
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.close()

    def _handle(self, path: str) -> tuple[int, dict[str, Any]]:
        action = SERVED_ENDPOINTS.get(path)
        if action is None:
            return 404, {"error": "unknown endpoint"}
        if action in self._failing_actions:
            return self._failure_status, {"action": action.value, "succeeded": False}
        with self._lock:
            result = self.executor.execute(action)
        return 200, {"action": action.value, "succeeded": result.succeeded}

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler.
                status, payload = server._handle(self.path)
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
                """Stay quiet; request paths are not part of the experiment record."""

        return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument(
        "--fail-action",
        action="append",
        default=[],
        choices=[item.value for item in Action],
        help="Return a failure status for the specified action to test error handling",
    )
    parser.add_argument("--failure-status", type=int, default=503)
    args = parser.parse_args(argv)

    server = PiStubServer(
        port=args.port,
        failing_actions=frozenset(Action(value) for value in args.fail_action),
        failure_status=args.failure_status,
    )
    print(f"{server.base_url} (Ctrl+C to stop)")
    try:
        with server:
            threading.Event().wait()
    except KeyboardInterrupt:
        print("Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
