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

### 권한 허용 전 (첫 시도)

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

### 권한 허용 후

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

이 150 frame 실행은 카메라 획득과 Tasks backend 실행 경로만 확인합니다. 사용자
상태 전이는 이 실행에서 검증하지 않았습니다(아래 내장 카메라 실행 참조). latency 값은
개발 호스트 측정치이므로 RQ3의 edge 근거로 사용하지 않습니다.

### 카메라 index 확인

`python -m sleep_aware.capture.smoke --list` 결과입니다.

| index | 장치 | shape | 평균 밝기 | 비고 |
|---|---|---|---|---|
| 0 | iPhone15,2 (연속성 카메라) | (480, 640, 3) | 0.1 | 검은 화면 경고 |
| 1 | MacBook Pro 카메라 | (480, 640, 3) | 112.5 | 정상 |

macOS가 연속성 카메라를 index 0으로 잡았고, 엎어 둔 iPhone에서 검은 frame이
들어왔습니다. 위의 150 frame 실행이 전부 `NO_FACE`였던 원인입니다. 코드 오류가 아니라
입력 장치 문제이며, 이후 실행은 내장 카메라(index 1)를 사용했습니다.

### CLI 카메라 실행 (내장 카메라, 사용자 있음)

- Command: `sleep-aware --input camera --actions mock --intention wake --no-display --max-frames 200 --camera-index 1`
- Result: `run_end.status=completed`, frame 200개, 30.0 FPS
- 상태 전이: `AWAKE → EYES_CLOSED → AWAKE → EYES_CLOSED → DROWSY → AWAKE`
- 상태 분포: AWAKE 26, EYES_CLOSED 148, DROWSY 26
- EAR: 200 frame 모두 기록, 범위 0.015 ~ 0.314
- inference latency: 중앙값 8.7ms, p95 12.9ms (개발 호스트 측정치이며 RQ3 edge 근거가 아니다)

실제 카메라 입력에서 `AWAKE → EYES CLOSED → DROWSY` 전이와 EAR 기록을 확인했습니다.
실제 장치(조명·부저·미디어) 동작은 이 실행에 포함되지 않습니다(`--actions mock`).

### 2026-09-19 검증 요약

| 항목 | 상태 | 근거 |
|---|---|---|
| 카메라 권한과 frame 획득 | 확인 | capture smoke 통과 |
| Tasks backend 실행 경로 | 확인 | 150 frame 실행, `run_end=completed` |
| camera index 구분(연속성 카메라 포함) | 확인 | `--list` 결과 |
| 사용자 상태 전이(`AWAKE → EYES CLOSED → DROWSY`) | 확인 | 내장 카메라 200 frame 실행 |
| 실제 장치(조명·부저·미디어) 동작 | 미실시 | 모든 실행이 `--actions mock` |
| Raspberry Pi 성능(RQ3) | 미실시 | 개발 호스트 측정치만 존재 |
