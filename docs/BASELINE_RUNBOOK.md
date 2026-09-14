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

Face Mesh processor는 native resource를 소유하므로 아래처럼 종료를 보장해야 합니다.

```python
from sleep_aware.pipeline import MediaPipeFaceMeshProcessor

with MediaPipeFaceMeshProcessor() as landmark_processor:
    # BaselinePipeline에 landmark_processor를 주입하여 실행합니다.
    ...
```

## Legacy 60/61-frame behavior

Legacy 구현은 연속 눈 감김 60번째 frame에서 화면 상태를 `DROWSY`로 바꾸고 61번째
frame부터 action을 실행했습니다. 30 FPS를 가정하면 첫 감김 frame을 0초로 볼 때 각각
약 1.967초와 2.000초이지만, 실제 지속 시간은 frame rate 변화에 따라 달라집니다.

새 fixed baseline은 frame count를 사용하지 않습니다. 첫 감김 관측의 monotonic
timestamp부터 `DROWSY_SECONDS`(기본 2.0초)가 경과하면 `DROWSY` 상태와 policy action을
같은 관측에서 생성합니다. 따라서 기본 30 FPS에서는 legacy의 61번째-frame action
시점에 대응하며, 낮거나 불규칙한 FPS에서도 시간 조건은 유지됩니다.

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
