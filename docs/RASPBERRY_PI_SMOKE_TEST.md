# Raspberry Pi HTTP smoke test

로컬 mock 검증과 실제 장치 검증을 분리한다. 개인 IP, 이메일 주소, 응답 본문,
자격 증명은 커밋하거나 실험 기록에 복사하지 않는다.

## 사전 조건

Raspberry Pi 서비스는 다음 상태 변경 API를 외부 네트워크 전체가 아닌 실험용
호스트에서만 접근할 수 있도록 제한하고, 모두 `POST`로 제공해야 한다.

| Action | Endpoint |
|---|---|
| `pause_media` | `/actions/media/pause` |
| `play_media` | `/actions/media/play` |
| `light_off` | `/actions/light/off` |
| `light_on` | `/actions/light/on` |
| `buzzer_alert` | `/actions/buzzer/alert` |
| `start_session` | `/actions/session/start` |
| `end_session` | `/actions/session/end` |

조명, 미디어, 세션 API는 같은 명령을 반복해도 최종 상태가 달라지지 않도록
구현한다. `buzzer_alert`는 호출마다 물리 동작이 발생하는 명령이므로 본질적으로
비멱등적이다. 정책의 전이 억제와 서버 측 짧은 중복 방지 창을 함께 사용한다.

## 로컬 mock 검증

네트워크와 장치를 사용하지 않는 검증 결과는 CI 및 PR의 테스트 결과로 기록한다.

```bash
python -m pytest tests/test_action_executors.py
```

`MockActionExecutor.state`에서 `light_on`, `buzzer_alert_count`,
`media_playing`, `session_active`를 확인한다.

## 하드웨어 없는 stub 검증

Raspberry Pi가 없을 때는 같은 endpoint를 loopback에서 제공하는 stub 서버로 HTTP
경로를 재현한다.

```bash
python -m sleep_aware.adapters.pi_stub_server --port 5050
PI_BASE_URL=http://127.0.0.1:5050 sleep-aware --input camera --actions real --intention wake
```

stub은 표준 라이브러리만 사용하며 `127.0.0.1`에만 bind한다. 응답은
`MockActionExecutor`의 상태를 그대로 반영한다. 실패 경로는 다음과 같이 재현한다.

```bash
# 특정 action에 503을 반환
python -m sleep_aware.adapters.pi_stub_server --fail-action buzzer_alert --failure-status 503
# 연결 실패는 stub을 중지한 뒤 실행
```

이 검증은 요청 경로, 상태 코드 처리, `connection_error` 복구만 확인한다. 조명,
부저, 미디어의 물리 동작은 확인하지 않으므로 실제 장치 검증으로 기록하지 않는다.
자동 검증 결과는 `tests/test_pi_stub_server.py`와
[HARDWARE_FREE_RESULTS.md](HARDWARE_FREE_RESULTS.md)에 있다.

## 실제 장치 검증

### 서비스 기동

Raspberry Pi에서 실행한다. 저장소 루트의 `.env`에서 `RELAY_PIN`, `BUZZER_PIN`을 읽는다.
최근 Raspberry Pi OS는 시스템 Python에 pip 설치를 막으므로 venv를 사용한다.

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e '.[raspberrypi]'
python -m sleep_aware.adapters.pi_service        # 기본 127.0.0.1:5050
```

Raspberry Pi 5에서는 `RPi.GPIO`가 `Cannot determine SOC peripheral base address` 오류로
실패한다고 알려져 있다. 같은 모듈 이름을 제공하는 `rpi-lgpio`로 교체한다. 이 교체는 아직
실제 장치에서 확인되지 않았다.

```bash
python -m pip uninstall -y RPi.GPIO && python -m pip install rpi-lgpio
```

서비스는 `SIGINT`, `SIGTERM`, `SIGHUP`에서 GPIO를 정리하지만 `kill -9`와 전원 차단에서는
정리하지 못한다. SSH 세션이 끊겨도 계속 실행하려면 `tmux` 안에서 실행한다.

기본값은 loopback이므로 호스트에서는 SSH 터널로 접근한다. 터널을 쓰면 `PI_BASE_URL`을
loopback으로 유지하므로 `--allow-insecure-http`가 필요 없다.

```bash
ssh -L 5050:127.0.0.1:5050 <pi-user>@<local-device-address>
```

격리된 망에서 직접 접근할 때만 `--host <Pi 주소>`로 bind하고, 호스트의 `sleep-aware`에
`--allow-insecure-http`를 붙인다. 이 옵션이 없으면 원격 `http://` 주소는 시작 시 거부된다.

서비스의 동작은 다음과 같다.

| 항목 | 동작 |
|---|---|
| 시작 | legacy와 같이 조명을 켠다 |
| `light_on` / `light_off` | active-low 릴레이 제어. on은 출력 LOW, off는 입력으로 전환(해제) |
| `buzzer_alert` | 2.5초 경보를 백그라운드에서 울리고 `202`로 즉시 응답. 5초 안의 중복 요청은 `200`과 `deduplicated: true` |
| `start_session` / `end_session` | 메모리에서 세션만 추적 |
| `pause_media` / `play_media` | **물리 동작 없음.** `200`과 `physical: false`로 응답하고 경고 로그를 남김 |
| 종료(`SIGINT`, `SIGTERM`, `SIGHUP`) | 진행 중인 경보 완료 후 부저 LOW, 릴레이 해제, GPIO cleanup. 실패 시 종료 코드 `1` |

경보는 기본 제한 시간 2초보다 길어 응답을 기다리면 `timeout`으로 기록되므로 백그라운드에서
실행한다. `202` 이후의 부저 실패는 JSONL에 남지 않고 서비스 로그의 `buzzer_alert_failed`로만
남는다. **`--actions real`의 JSONL에서 미디어 action이 성공이어도 미디어가 실제로 제어된 것은
아니다.** 미디어의 물리 동작은 `--actions host`로만 검증한다.

호스트의 CLI가 종료되어도 Raspberry Pi의 GPIO는 해제되지 않는다. CLI 종료 시 정리되는 것은
정책이 소유한 세션과 미디어뿐이고, 릴레이 해제와 GPIO cleanup은 서비스를 종료할 때 일어난다.

### 검증 절차

1. 호스트의 커밋하지 않는 `.env`에 주소와 제한 시간을 설정한다. `.env`는 현재 작업
   디렉터리에서 읽으며, 이미 설정된 환경 변수가 우선한다.

   ```dotenv
   PI_BASE_URL=http://127.0.0.1:5050
   PI_TIMEOUT_SECONDS=2.0
   ```

2. Raspberry Pi와 실험용 호스트가 격리된 네트워크에 있는지, API가 인터넷에
   공개되지 않았는지 확인한다.
3. 각 endpoint를 한 번씩 호출하고 조명, 부저, 세션 상태를 직접 확인한다.
   부저는 주변에 알린 뒤 마지막에 한 번만 호출한다.
   `pytest tests/test_action_executors.py`는 가짜 transport를 쓰므로 이 단계를 대신하지 못한다.

   ```bash
   curl -i -X POST http://127.0.0.1:5050/actions/light/off
   ```

4. 정상 응답의 상태 코드를 기록한다. `succeeded`, `status_code`, `elapsed_ms`는 CLI 실행
   시의 action 결과에서 확인한다.
5. 서비스를 잠시 중지한 뒤 한 번 호출하여 `error_reason=connection_error`가
   기록되고 detection pipeline이 다음 관측을 계속하는지 확인한다.
6. `docs/EXPERIMENT_LOG_TEMPLATE.md`의 **실제 장치 검증** 절에 날짜, 익명 장치
   식별자, 소프트웨어 버전, 결과만 기록한다. 로컬 mock 결과와 합쳐 쓰지 않는다.

### RQ3 측정 시 추가 준비

Raspberry Pi에서 파이프라인까지 실행하려면 카메라와 MediaPipe가 필요하다. `host` extra와
모델 파일을 추가로 준비한다. 이 환경의 설치 가능 여부는 아직 실제 장치에서 확인되지 않았다.
MediaPipe는 64-bit OS(`uname -m`이 `aarch64`)를 전제로 하며, 32-bit OS에서는 설치되지 않은
사례가 있다. Python 버전에 맞는 wheel이 없으면 설치가 실패하므로 실패 내용을 그대로 기록한다.

```bash
python -m pip install -e '.[host]'
python -m sleep_aware.pipeline.face_landmarker --download
python -m sleep_aware.capture.smoke --list
```

카메라는 `cv2.VideoCapture`로 연다. USB 웹캠을 우선 사용한다. CSI 카메라 모듈은 libcamera
스택을 쓰므로 `rpicam-hello`가 동작해도 `VideoCapture`로는 frame을 받지 못할 수 있다.
`smoke --list`에서 frame이 나오지 않으면 그 사실을 기록한다.

화면 없는 환경에서는 `--no-display`가 필수다. 없으면 시작 시 오류로 종료한다.

CPU와 memory는 JSONL에 없으므로 별도로 기록한다. 예를 들어 `sysstat`의 `pidstat`을 쓸 수 있다.

```bash
pidstat -u -r -h -p <sleep-aware pid> 1 > results/pidstat-<run_id>.txt
```

실제 주소, HTTP 응답 본문, 참가자 또는 이메일 정보는 결과 파일에도 남기지 않는다.
