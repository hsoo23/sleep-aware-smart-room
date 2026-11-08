# Camera and Chrome Smoke-Test Results

These are development-host observations, not automated CI results or Raspberry Pi edge measurements. Unless stated otherwise, all camera runs used `--actions mock`, so they did not actuate physical devices.

## 2026-09-12: camera access denied

- Git commit before changes: `2debdf2`
- Command: `PYTHONPATH=src python -m sleep_aware.capture.smoke --frames 3`
- Requested camera: index 0, 640×480
- Result: the host denied capture permission before a usable device or returned resolution could be identified. The adapter reported `CameraOpenError` (`failed to open camera index 0`) and exited with code 1.
- Interpretation: unavailable-camera error path only; no successful frame capture.

## 2026-09-19: camera and Face Landmarker

The worktree was based on `36ed98b` and included the Tasks backend changes in the then-current PR.

### Before camera permission

The camera opened, but `PYTHONPATH=src python -m sleep_aware.capture.smoke --frames 3` failed to read frame 0. The error path moved from camera open to frame read. Access was then granted under macOS **System Settings → Privacy & Security → Camera**. This first attempt did not establish frame capture.

### After camera permission

| Check | Command or configuration | Recorded result | Limit |
|---|---|---|---|
| Capture smoke | `PYTHONPATH=src python -m sleep_aware.capture.smoke --frames 3` | Passed; index 0, 3 frames, shape `(480, 640, 3)`, monotonic duration 0.090 s | Camera capture only |
| Tasks backend CLI | `sleep-aware --input camera --actions mock --intention wake --no-display --max-frames 150` | `run_end.status=completed`; 150 frames in about 6.2 s (~24 FPS); inference latency median 2.4 ms, p95 3.7 ms | No person present; all states `NO_FACE`, no EAR |
| Built-in MacBook camera CLI | `sleep-aware --input camera --actions mock --intention wake --no-display --max-frames 200 --camera-index 1` | `run_end.status=completed`; 200 frames, 30.0 FPS; state sequence `AWAKE → EYES_CLOSED → AWAKE → EYES_CLOSED → DROWSY → AWAKE` | Mock actions; no physical devices |

Camera enumeration with `python -m sleep_aware.capture.smoke --list` found:

| Index | Device | Shape | Mean brightness | Interpretation |
|---|---|---|---:|---|
| 0 | iPhone15,2 Continuity Camera | `(480, 640, 3)` | 0.1 | Black-frame warning |
| 1 | MacBook Pro camera | `(480, 640, 3)` | 112.5 | Usable |

macOS selected the face-down iPhone as index 0, explaining the all-`NO_FACE` 150-frame run. The later 200-frame run used index 1. Its state counts were AWAKE 26, EYES_CLOSED 148, and DROWSY 26. EAR was recorded on all 200 frames, range 0.015–0.314. The recorded inference latency was median 8.7 ms and p95 12.9 ms **on the development host**. These observations verify camera input and state transitions, not Raspberry Pi RQ4 performance or physical lamp/buzzer/media behavior.

## 2026-09-19: macOS Chrome media control

The test used macOS, Google Chrome 153.0.8010.48, and one YouTube watch tab, with **View → Developer → Allow JavaScript from Apple Events** enabled. The code was `main` plus the AppleScript syntax fix in the then-current PR.

| Step | Script return | Observed video |
|---|---|---|
| Initial | — | playing |
| `play_media` | `play` | playing |
| `pause_media` | `pause` | paused |

All three tested calls (`pause_media`, `play_media`, `pause_media`) returned `succeeded=True`, with durations of 131–166 ms. The prior syntax `execute javascript ... in t` had produced `-1723`, which could be mistaken for a permission error; the corrected syntax passes the tab directly: `execute t javascript "..."`. This check did not include Pi light, buzzer, or session effects.

## Verification summary

| Scope | Status |
|---|---|
| Development-host camera permission and frame capture | Observed |
| MediaPipe Tasks backend path and user state transitions | Observed on development host |
| macOS Chrome media action | Observed separately |
| Combined MacBook-to-Pi physical closed loop | Not recorded here |
| Raspberry Pi 4 inference and resource use | Not recorded here |
