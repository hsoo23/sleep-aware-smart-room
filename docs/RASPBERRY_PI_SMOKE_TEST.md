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

1. 커밋하지 않는 `.env`에 실제 주소와 제한 시간을 설정한다.

   ```dotenv
   PI_BASE_URL=http://<local-device-address>:5050
   PI_TIMEOUT_SECONDS=2.0
   ```

2. Raspberry Pi와 실험용 호스트가 격리된 네트워크에 있는지, API가 인터넷에
   공개되지 않았는지 확인한다.
3. 각 endpoint를 한 번씩 호출하고 조명, 부저, 미디어, 세션 상태를 직접 확인한다.
   부저는 주변에 알린 뒤 마지막에 한 번만 호출한다.
4. 정상 응답의 `succeeded`, `status_code`, `elapsed_ms`를 기록한다.
5. 서비스를 잠시 중지한 뒤 한 번 호출하여 `error_reason=connection_error`가
   기록되고 detection pipeline이 다음 관측을 계속하는지 확인한다.
6. `docs/EXPERIMENT_LOG_TEMPLATE.md`의 **실제 장치 검증** 절에 날짜, 익명 장치
   식별자, 소프트웨어 버전, 결과만 기록한다. 로컬 mock 결과와 합쳐 쓰지 않는다.

실제 주소, HTTP 응답 본문, 참가자 또는 이메일 정보는 결과 파일에도 남기지 않는다.
