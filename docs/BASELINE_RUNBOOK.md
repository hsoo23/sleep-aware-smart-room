# Baseline Runbook

## Scope

This runbook separates the original integrated demonstration from local
software checks. A successful local check does not prove camera, GPIO, relay,
buzzer, Chrome, or email operation.

## Hardware demonstration

The original implementation is preserved in `legacy/`.

1. On Raspberry Pi, install the legacy requirements and run `python pi_server.py`.
2. On the host Mac, create the SSH tunnel described in `legacy/README.md`.
3. Update the local project path and Conda environment in `legacy/launcher_server.py`.
4. Run `python legacy/launcher_server.py` from the host environment.
5. Open `legacy/index.html` in Google Chrome.
6. Demonstrate Sleep Aid Mode and Wake-up Mode separately.
7. Record the selected mode, visible state transitions, device actions, recovery,
   and the Git commit used for the demonstration.

Do not commit video, participant data, email credentials, local IP addresses, or
machine-specific paths.

## Local software verification

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q
```

The unit tests cover EAR geometry, time-based temporal state transitions, and
the pure intention-aware policy. They do not validate physical devices.

## Camera smoke test

Run this separately on a development host with a webcam and the `host` extra
installed:

```bash
python -m sleep_aware.capture.smoke --camera-index 0 --width 640 --height 480
```

The command opens the configured camera, reads 30 frames by default, reports
the returned image shape and elapsed monotonic time, and releases the camera on
both success and failure. Record the date, operating system, camera model,
requested resolution, returned image shape, frame count, result, and Git commit
in [CAMERA_SMOKE_RESULTS.md](CAMERA_SMOKE_RESULTS.md). Do not treat this manual
result as a CI check.

## Demonstration checklist

- [ ] The mode is selected before detection starts.
- [ ] `AWAKE -> EYES CLOSED -> DROWSY` is visible.
- [ ] Sleep Aid pauses media and turns the lamp off without a buzzer.
- [ ] Wake-up pauses media, keeps the lamp on, and sounds the buzzer.
- [ ] The user is observed again after actuation.
- [ ] Sleep Aid records the end event/report, or Wake-up resumes media.
- [ ] The run records date, mode, detector version, hardware, and commit hash.
