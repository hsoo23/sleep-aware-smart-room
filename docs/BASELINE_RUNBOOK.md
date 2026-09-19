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

## Phase 2 CLI 실행

먼저 하드웨어 없는 두 폐루프를 실행합니다.

```bash
sleep-aware --input mock --actions mock --intention sleep
sleep-aware --input mock --actions mock --intention wake
```

각 명령의 마지막 출력은 JSONL 로그 경로입니다. 두 로그 모두 다음을 확인합니다.

- `run_start`에 run ID, detector 설정, 플랫폼, Git commit이 있다.
- 상태가 `AWAKE → EYES_CLOSED → DROWSY → AWAKE` 순서로 나타난다.
- Sleep은 `pause_media, light_off, start_session` 후 `end_session`을 실행한다.
- Wake는 `pause_media, light_on, buzzer_alert` 후 `play_media`를 실행한다.
- 마지막 `run_end.status`가 `completed`이다.

### macOS Chrome 미디어 제어 사전 설정

`--actions host`로 미디어를 이 호스트에서 제어하려면 Chrome 설정을 먼저 켜야 합니다.

1. Chrome 메뉴 → 보기 → 개발자용 → **Apple Events에서 JavaScript 허용**
2. 터미널(또는 실행 중인 앱)에 Chrome 제어 권한 허용: 시스템 설정 → 개인정보 보호 및
   보안 → 자동화
3. YouTube 탭을 열어 둔다.

설정이 꺼져 있으면 AppleScript가 오류 `-1723`을 반환하고, 실행기는
`error_reason=javascript_not_allowed`와 함께 위 설정 경로를 기록한다. YouTube 탭이
없으면 `tab_not_found`, 탭은 있으나 video 요소가 없으면 `media_not_found`로 구분된다.

실제 카메라와 Raspberry Pi는 아래 명령으로 검증합니다.

```bash
sleep-aware --input camera --actions real --intention sleep --display
sleep-aware --input camera --actions real --intention wake --display
```

`--actions`는 어떤 장치가 실제로 동작하는지 결정합니다.

| 값 | 미디어 | 조명·부저 | 세션 | 필요한 환경 |
|---|---|---|---|---|
| `mock` | 메모리 | 메모리 | 메모리 | 없음 |
| `real` | Raspberry Pi HTTP | Raspberry Pi HTTP | Raspberry Pi HTTP | Raspberry Pi 서비스 |
| `host` | 이 호스트의 macOS Chrome | Raspberry Pi HTTP | 로컬 세션 추적기 | macOS + Chrome, Raspberry Pi 서비스 |

`host`는 미디어를 시연 호스트에서 직접 제어할 때 사용합니다. macOS가 아니면 미디어 action이
`unsupported_platform`으로 기록되고 나머지 action은 그대로 실행됩니다.

`q` 또는 Escape로 정상 종료합니다. 실패 시 기록 방법은 실패 시점에 따라 다릅니다.

- **로그 초기화 이후 실패**: CLI는 카메라·MediaPipe보다 먼저 JSONL 로그를 엽니다. 따라서
  카메라 권한·열기, MediaPipe 초기화, 실행 중 오류, 종료 cleanup 실패는
  `run_end.status=failed`와 `error_type`으로 남습니다. CLI 오류 메시지와 함께 기록합니다.
- **로그 초기화 실패**: 로그 디렉터리 생성이나 파일 열기가 실패하면 JSONL 파일과
  `run_end`가 만들어지지 않고 CLI 오류 경로로 종료합니다. 이때는 로그 경로 칸에
  `JSONL unavailable`과 CLI 오류 메시지를 기록합니다.

mock 성공을 실제 카메라·HTTP·GPIO 성공으로 보고하지 않습니다.

The unit tests cover EAR geometry, time-based temporal state transitions, and
the MediaPipe adapter boundary using a fake native model, and the pure
intention-aware policy. They do not validate a physical camera or devices.

## Fixed-EAR and Face Mesh settings

다음 환경 변수로 fixed baseline을 재현할 수 있습니다. 기본 EAR threshold는 legacy와
동일한 `0.21`입니다.

```text
EAR_THRESHOLD=0.21
DROWSY_SECONDS=2.0
RECOVERY_SECONDS=0.5
FACE_MESH_MAX_NUM_FACES=1
FACE_MESH_REFINE_LANDMARKS=true
FACE_MESH_MIN_DETECTION_CONFIDENCE=0.5
FACE_MESH_MIN_TRACKING_CONFIDENCE=0.5
```

Landmark processor는 OpenCV와 MediaPipe가 필요하므로 먼저 `host` extra를 설치합니다.

```bash
python -m pip install -e '.[dev,host]'
```

MediaPipe는 배포 버전에 따라 제공하는 API가 다릅니다.

| 설치된 MediaPipe | 사용하는 backend | 모델 파일 |
|---|---|---|
| legacy `mediapipe.solutions` 포함 | `MediaPipeFaceMeshProcessor` | 불필요 |
| Tasks API만 포함 (최근 wheel) | `MediaPipeFaceLandmarkerProcessor` | `face_landmarker.task` 필요 |

`create_landmark_processor()`가 설치된 버전을 확인해 backend를 고르므로 실행 명령은
같습니다. Tasks backend를 쓰는 환경에서는 모델을 한 번 내려받습니다. 모델 파일은
Git 무시 대상인 `models/`에 저장하며 커밋하지 않습니다.

```bash
python -m sleep_aware.pipeline.face_landmarker --download
```

경로를 바꾸려면 `FACE_LANDMARKER_MODEL` 또는 `--face-landmarker-model`을 사용합니다.
두 backend 모두 같은 눈 index와 pixel 좌표를 반환하므로 EAR, 상태 판정, 로그 형식은
동일합니다. `refine_landmarks` 설정은 legacy backend에만 적용되며 Tasks 모델은 항상
478개 landmark를 반환합니다.

Landmark processor는 native resource를 소유하므로 아래처럼 종료를 보장해야 합니다.

```python
from sleep_aware.config import settings
from sleep_aware.pipeline import create_landmark_processor

with create_landmark_processor(model_path=settings.face_landmarker_model) as processor:
    # BaselinePipeline에 processor를 주입하여 실행합니다.
    ...
```

`--no-display`로 카메라를 실행하면 종료 조건이 없으므로 `--max-frames`로 frame 수를
제한해 재현 가능한 길이의 기록을 남길 수 있습니다.

```bash
sleep-aware --input camera --actions mock --intention wake --no-display --max-frames 150
```

## Legacy 60/61-frame behavior

Legacy 구현은 연속 눈 감김 60번째 frame에서 화면 상태를 `DROWSY`로 바꾸고 61번째
frame부터 action을 실행했습니다. 30 FPS를 가정하면 첫 감김 frame을 0초로 볼 때 각각
약 1.967초와 2.000초이지만, 실제 지속 시간은 frame rate 변화에 따라 달라집니다.

새 fixed baseline은 frame count를 사용하지 않습니다. 첫 감김 관측의 monotonic
timestamp부터 `DROWSY_SECONDS`(기본 2.0초)가 경과하면 `DROWSY` 상태와 policy action을
같은 관측에서 생성합니다. 따라서 기본 30 FPS에서는 legacy의 61번째-frame action
시점에 대응하며, 낮거나 불규칙한 FPS에서도 시간 조건은 유지됩니다.

## 카메라 선택

macOS는 근처에 iPhone이 있으면 연속성 카메라를 index 0으로 잡습니다. 이때 iPhone이
엎어져 있거나 잠겨 있으면 검은 frame이 들어오고, 파이프라인은 오류 없이 `NO_FACE`만
기록합니다. 실험 기록만 보면 "얼굴을 찾지 못했다"로 보이므로 실행 전에 index를
확인한다.

```bash
python -m sleep_aware.capture.smoke --list
```

각 index의 해상도와 평균 밝기를 출력하고, 검은 화면이면 경고를 표시한다. 내장
카메라를 쓰려면 확인한 index를 `--camera-index` 또는 `CAMERA_INDEX`로 지정한다.
`sleep_aware.capture.smoke`는 단일 index 실행에서도 마지막 frame이 검은 화면이면
경고와 함께 종료 코드 `2`를 반환한다.

시연 기록에는 사용한 camera index와 장치 종류(내장 카메라 또는 연속성 카메라)를
반드시 적는다. 두 장치는 해상도와 FPS가 다르므로 latency 비교에 영향을 준다.

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

The unit tests also cover the structured log schema, but do not validate
physical devices.

To produce a hardware-free structured log under the Git-ignored `results/logs/`:

```bash
python -m sleep_aware.eventlog.mock_run
```

See [LOGGING_SCHEMA.md](LOGGING_SCHEMA.md) for the record format.

## Demonstration checklist

- [ ] The mode is selected before detection starts.
- [ ] `AWAKE -> EYES CLOSED -> DROWSY` is visible.
- [ ] `NO_FACE`가 처리 오류로 잘못 기록되지 않는다.
- [ ] log에 좌·우·평균 EAR와 landmark/inference latency가 기록된다.
- [ ] Sleep Aid pauses media and turns the lamp off without a buzzer.
- [ ] Wake-up pauses media, keeps the lamp on, and sounds the buzzer.
- [ ] The user is observed again after actuation.
- [ ] Sleep Aid records the end event/report, or Wake-up resumes media.
- [ ] The run records date, mode, detector version, hardware, and commit hash.

상세 시연 기록과 연구 질문 연결은 [DEMO_VALIDATION.md](DEMO_VALIDATION.md)를
사용합니다.
