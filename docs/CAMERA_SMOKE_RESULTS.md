# Camera Smoke Test Results

Camera smoke results are recorded separately from automated test results because
they depend on host permissions and attached hardware.

## 2026-09-12 development workspace

- Git commit before changes: `2debdf2`
- Command: `PYTHONPATH=src python -m sleep_aware.capture.smoke --frames 3`
- Requested camera index: `0`
- Requested resolution: `640x480`
- Result: not completed; the host denied camera capture permission before a
  device or returned resolution could be identified
- Adapter behavior: reported `CameraOpenError` as
  `failed to open camera index 0` and exited with status `1`
- Follow-up: grant camera permission to the terminal/runtime and repeat the
  command on the target development host

This result verifies the unavailable-camera error path, not successful physical
frame capture.
