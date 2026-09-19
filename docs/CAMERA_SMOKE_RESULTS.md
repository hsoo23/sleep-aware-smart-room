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

## 2026-09-19 development workspace

- Git commit: `36ed98b`
- Command: `PYTHONPATH=src python -m sleep_aware.capture.smoke --frames 3`
- Requested camera index: `0`
- Requested resolution: `640x480`
- Result: not completed; the camera opened but the first frame could not be read
  (`failed to read frame 0 from camera index 0`), which is the expected behavior
  when the host has not granted camera access to the running terminal
- Difference from 2026-09-12: the open step now succeeds, so the failure moved
  from `CameraOpenError` to the frame-read path
- Follow-up: grant camera access to the terminal in macOS 설정 → 개인정보 보호 및
  보안 → 카메라, then repeat the command and record the returned image shape

이 결과도 실패 경로 확인이며 실제 frame 획득 검증이 아니다.
