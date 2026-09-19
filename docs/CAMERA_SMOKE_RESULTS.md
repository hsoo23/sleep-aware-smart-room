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

- Git commit: `36ed98b` 기준, 이 PR의 Tasks backend 변경 포함
- 카메라 권한을 허용한 뒤 재시도했습니다.

### capture smoke

- Command: `PYTHONPATH=src python -m sleep_aware.capture.smoke --frames 3`
- Result: 통과. index 0, 3 frames, 반환 shape `(480, 640, 3)`, monotonic duration 0.090s

### CLI 카메라 실행 (Tasks backend)

- Command: `sleep-aware --input camera --actions mock --intention wake --no-display --max-frames 150`
- Result: `run_end.status=completed`, frame 150개, 약 24 FPS (6.2초)
- inference latency: 중앙값 2.4ms, p95 3.7ms
- 카메라 앞에 사람이 없어 상태는 전부 `NO_FACE`였고 EAR은 기록되지 않았습니다.

카메라 획득과 Tasks backend 실행 경로는 확인했습니다. 실제 사용자의
`AWAKE → EYES CLOSED → DROWSY` 상태 전이는 아직 `미실시`이며, latency 값은 개발
호스트 측정치이므로 RQ3의 edge 근거로 사용하지 않습니다.
