# Fixed-EAR Baseline Runbook

## Purpose and scope

This runbook covers the Phase 2 B0 baseline. It distinguishes software-only checks, development-host camera/Chrome observations, and physical Raspberry Pi validation. A green CI run or mock trace does not establish camera, GPIO, relay, buzzer, or complete end-to-end operation.

The original class-project stack is preserved in [legacy/README.md](../legacy/README.md). Its dashboard and servers use the original APIs and are separate from the current CLI.

## 1. Install and check the software

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check src tests
python -m compileall -q src tests
python -m pytest -q
```

Run both deterministic closed loops without hardware:

```bash
sleep-aware --input mock --actions mock --intention sleep
sleep-aware --input mock --actions mock --intention wake
```

The final line printed by each command is its JSONL log path. Check that `run_start` includes run ID, detector configuration, platform, and Git commit; the sequence reaches `AWAKE → EYES_CLOSED → DROWSY → AWAKE`; Sleep emits `pause_media, light_off, start_session, end_session`; Wake emits `pause_media, light_on, buzzer_alert, play_media`; and `run_end.status` is `completed`. Mock execution proves the software path only.

## 2. Prepare the camera host

Install the optional camera/MediaPipe dependencies:

```bash
python -m pip install -e '.[host]'
python -m sleep_aware.capture.smoke --list
```

The camera probe reports each index, image shape, and mean brightness. On macOS, an iPhone Continuity Camera may occupy index 0 and return black frames; choose a usable index and record the device. The probe returns exit code `2` when its final frame is black.

`create_landmark_processor()` uses legacy `mediapipe.solutions` when available; otherwise it uses the Tasks Face Landmarker backend. The Tasks backend needs a model file:

```bash
python -m sleep_aware.pipeline.face_landmarker --download
```

The model is saved under Git-ignored `models/`. Set `FACE_LANDMARKER_MODEL` or `--face-landmarker-model` for a different path. Both backends return compatible eye landmarks. The `refine_landmarks` setting applies only to the legacy backend. Close the processor after use; the CLI handles this automatically.

Check the camera-to-detector path with mock actions:

```bash
sleep-aware --input camera --actions mock --intention wake --camera-index 0 --no-display --max-frames 150
```

Replace index 0 with the verified value. This run does not actuate a lamp or buzzer.

## 3. Prepare Raspberry Pi actions

Follow [RASPBERRY_PI_SMOKE_TEST.md](RASPBERRY_PI_SMOKE_TEST.md) for wiring, Pi installation, service startup, SSH tunnel, and direct endpoint checks. The Pi action service starts the lamp, handles GPIO and HTTP actions, and does **not** perform face inference by itself.

On the host, copy `.env.example` to an untracked `.env`; check `PI_BASE_URL`, `PI_TIMEOUT_SECONDS`, camera settings, and detector parameters. The service reads `RELAY_PIN` and `BUZZER_PIN` from its own working directory's `.env`. Existing environment variables take precedence.

```text
EAR_THRESHOLD=0.21
DROWSY_SECONDS=2.0
RECOVERY_SECONDS=0.5
FACE_MESH_MAX_NUM_FACES=1
FACE_MESH_REFINE_LANDMARKS=true
FACE_MESH_MIN_DETECTION_CONFIDENCE=0.5
FACE_MESH_MIN_TRACKING_CONFIDENCE=0.5
```

The legacy prototype displayed `DROWSY` on the 60th consecutive closed-eye frame and actuated on the 61st. At an assumed 30 FPS these are about 1.967 s and 2.000 s from the first closed-eye observation. The new baseline uses elapsed monotonic time: it emits `DROWSY` and actions together after `DROWSY_SECONDS` (default 2.0 s). The actual time remains stable when frame rate changes.

## 4. Prepare host media control

For `--actions host`, open a YouTube video in Google Chrome on macOS. Enable Chrome **View → Developer → Allow JavaScript from Apple Events**, then allow automation access for the terminal or application under macOS **System Settings → Privacy & Security → Automation**. Menu wording may vary by OS language.

A `-1723` AppleScript error is classified as `javascript_not_allowed`, but can also indicate script syntax failure; inspect both if the setting is already enabled. `tab_not_found` means no YouTube tab was found; `media_not_found` means the tab has no video element.

| `--actions` | Media | Lamp and buzzer | Session |
|---|---|---|---|
| `mock` | In-memory | In-memory | In-memory |
| `real` | Pi HTTP acknowledgement; no physical media action | Pi HTTP / GPIO | Pi service memory |
| `host` | This host's macOS Chrome | Pi HTTP / GPIO | Host memory |

On non-macOS platforms, `--actions host` reports `unsupported_platform` for media actions. For a complete host/Pi demonstration use:

```bash
sleep-aware --input camera --actions host --intention sleep --camera-index 0
sleep-aware --input camera --actions host --intention wake --camera-index 0
```

Run one mode at a time. Verify camera index and physical devices first. For a headless run use `--no-display --max-frames N`; otherwise quit with `q` or Escape.

## 5. Record and interpret results

The CLI opens its JSONL log before camera and MediaPipe initialization. Failures after logger startup appear as `run_end.status=failed` and `error_type`. If the logger itself cannot create a file, record `JSONL unavailable` and the CLI error. A missing face yields `NO_FACE`; it is distinct from a processing failure.

```bash
python -m sleep_aware.eventlog.summary results/logs/<run_id>.jsonl
```

The summary reports states, actions, FPS, and latency. Report action-frame control latency separately because most frames contain no action. CPU and memory require an external measurement on the Pi. Never label host measurements as Raspberry Pi edge evidence.

Use [DEMO_VALIDATION.md](DEMO_VALIDATION.md) for the dated physical checklist and results; use [HARDWARE_FREE_RESULTS.md](HARDWARE_FREE_RESULTS.md) for software-only evidence. The observed phase transitions should be `AWAKE → EYES_CLOSED → DROWSY`, followed by re-observation and recovery. Confirm `NO_FACE` is not recorded as a processing error, and confirm the intended media, lamp, buzzer, and session effects in both modes. Keep participant media, credentials, network addresses, and machine-specific paths out of Git.
