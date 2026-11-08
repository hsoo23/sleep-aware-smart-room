# Raspberry Pi Action Service and Physical Verification

This guide keeps local mock/stub checks separate from physical-device observations. Do not commit personal IP addresses, credentials, HTTP response bodies, participant data, or machine-specific paths.

A dated summary of the team-reported physical demonstration and its validated
JSONL runs is in [PHYSICAL_DEMO_2026-11-05.md](PHYSICAL_DEMO_2026-11-05.md).

## HTTP contract

The Pi service accepts state-changing requests by `POST` only. By default it binds to loopback; access it from the host through an SSH tunnel.

| Action | Endpoint |
|---|---|
| `pause_media` | `/actions/media/pause` |
| `play_media` | `/actions/media/play` |
| `light_off` | `/actions/light/off` |
| `light_on` | `/actions/light/on` |
| `buzzer_alert` | `/actions/buzzer/alert` |
| `start_session` | `/actions/session/start` |
| `end_session` | `/actions/session/end` |

Light, media, and session commands are intended to be idempotent. `buzzer_alert` is physically non-idempotent, so the policy suppresses repeat transitions and the service deduplicates requests briefly.

## Software-only checks

```bash
python -m pytest tests/test_action_executors.py tests/test_pi_stub_server.py
python -m sleep_aware.adapters.pi_stub_server --port 5050
```

The stub provides the same endpoints on `127.0.0.1` without GPIO. In a separate terminal, use the camera CLI or a request client to check HTTP behavior. To simulate a failure:

```bash
python -m sleep_aware.adapters.pi_stub_server --fail-action buzzer_alert --failure-status 503
```

These checks cover request paths, status codes, retries, and connection errors. They do **not** show physical lamp, buzzer, or media control. See [HARDWARE_FREE_RESULTS.md](HARDWARE_FREE_RESULTS.md).

## Physical setup and service

The configured pin numbers are BCM identifiers. The documented reference wiring is:

| Connection | BCM | Physical Pi 40-pin header |
|---|---|---|
| Relay module input, active-low | GPIO17 | Pin 11 |
| Buzzer control | GPIO18 | Pin 12 |

`RELAY_PIN` and `BUZZER_PIN` in the Pi's `.env` can change the BCM pins. Check the actual relay module and load wiring before power-up; these two signal rows alone are not a complete power-circuit diagram. The active-low implementation drives the input LOW to turn the lamp on and releases the pin to input mode to turn it off. A board with a different polarity behaves differently.

On Raspberry Pi, from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[raspberrypi]'
python -m sleep_aware.adapters.pi_service
```

The service reads `.env` from its current working directory and defaults to `127.0.0.1:5050`. Raspberry Pi OS may require a virtual environment for pip installs. For Pi 5, the documented `RPi.GPIO` compatibility issue may require `rpi-lgpio`; that replacement has not been physically validated in this project.

```bash
python -m pip uninstall -y RPi.GPIO
python -m pip install rpi-lgpio
```

The service handles `SIGINT`, `SIGTERM`, and `SIGHUP` cleanup, but cannot handle `kill -9` or sudden power loss. Run it under `tmux` if it must survive an SSH disconnect. From the host, maintain this tunnel in a separate terminal:

```bash
ssh -L 5050:127.0.0.1:5050 <pi-user>@<local-device-address>
```

With the tunnel, leave `PI_BASE_URL=http://127.0.0.1:5050`; `--allow-insecure-http` is unnecessary. Direct plain-HTTP access on an isolated test network requires an explicit Pi bind address and `--allow-insecure-http` on the host CLI.

| Event | Service behavior |
|---|---|
| Startup | Sets the lamp on, as in the legacy prototype |
| `light_on` / `light_off` | Active-low relay: output LOW / release to input |
| `buzzer_alert` | Starts a 2.5 s alert asynchronously and replies `202`; duplicates within 5 s reply `200` with `deduplicated: true` |
| `start_session` / `end_session` | Tracks a session in memory only |
| `pause_media` / `play_media` | Replies `200` with `physical: false`; no physical media action |
| Service shutdown | Waits for an alert, sets buzzer LOW, releases relay, and cleans up GPIO |

A `202` response confirms that the alert was scheduled, not that its full sound completed. A later buzzer failure is logged by the service as `buzzer_alert_failed`, not by the host JSONL. Likewise, a successful media action under `--actions real` does **not** prove media control; verify media using `--actions host` on macOS. Stopping the host CLI does not release Pi GPIO; service shutdown performs that cleanup.

## Physical verification checklist

1. Confirm the Pi and host use the intended isolated network. Keep the API off the public internet.
2. On the host, set an untracked `.env` or equivalent environment variables:
   ```dotenv
   PI_BASE_URL=http://127.0.0.1:5050
   PI_TIMEOUT_SECONDS=2.0
   ```
3. With the service running and the tunnel open, call each endpoint and **observe** lamp, buzzer, and session effects. Warn nearby people before the single buzzer check. The mock action tests do not replace this step.
   ```bash
   curl -i -X POST http://127.0.0.1:5050/actions/light/off
   curl -i -X POST http://127.0.0.1:5050/actions/light/on
   ```
4. Record the HTTP status and the CLI action result fields `succeeded`, `status_code`, and `elapsed_ms` where applicable.
5. Stop the service briefly and confirm that a request records `connection_error` while the detection pipeline can continue re-observing.
6. Run both full Sleep Aid and Wake-up cases with `--actions host`; verify actuation, re-observation, recovery, and restoration. Record results in [DEMO_VALIDATION.md](DEMO_VALIDATION.md) and [EXPERIMENT_LOG_TEMPLATE.md](EXPERIMENT_LOG_TEMPLATE.md).

Do not mark a checklist item complete from a successful mock/stub test. Record failures and unperformed checks explicitly.

## Raspberry Pi 4 edge inference: RQ4 and RQ5

The action service does not execute AI inference. For a Pi 4 edge run, install `.[host]` on the Pi, obtain the Face Landmarker model if needed, and verify a camera with `python -m sleep_aware.capture.smoke --list`. MediaPipe wheel availability depends on the Pi OS architecture and Python version; record installation failures rather than implying a successful edge deployment. A USB webcam is the first supported camera path via `cv2.VideoCapture`; a CSI camera may require additional integration.

```bash
python -m pip install -e '.[host]'
python -m sleep_aware.pipeline.face_landmarker --download
python -m sleep_aware.capture.smoke --list
sleep-aware --input camera --actions mock --intention wake --no-display --max-frames 300
```

A headless Pi requires `--no-display`. The JSONL log and summary provide FPS, inference latency, action-frame control latency, and end-to-end latency:

```bash
python -m sleep_aware.eventlog.summary results/logs/<run_id>.jsonl
```

CPU and memory are not recorded in JSONL. Collect them separately on the **same Pi run**, for example with `pidstat`:

```bash
pidstat -u -r -h -p <sleep-aware-pid> 1 > results/pidstat-<run_id>.txt
```

Report the measurement tool, process, run ID, sample count, median and p95 latency, CPU, and memory. Whole-run control latency is dominated by frames without actions; use action-frame latency to assess device control. The current repository does not contain completed Pi edge measurements.

Do not copy private network addresses, response bodies, or participant identifiers into shared result files.
