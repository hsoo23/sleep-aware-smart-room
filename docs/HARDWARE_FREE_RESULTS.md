# 하드웨어 없는 검증 결과

이 문서는 카메라, Raspberry Pi, 릴레이, 부저 없이 수행한 검증 결과만 기록한다.
실제 장치 결과는 [DEMO_VALIDATION.md](DEMO_VALIDATION.md)와
[CAMERA_SMOKE_RESULTS.md](CAMERA_SMOKE_RESULTS.md)에 분리해 기록하며, 이 문서의
결과를 하드웨어 검증으로 보고하지 않는다.

## mock 반복 실행 재현성 (RQ1)

- 날짜: 2026-09-19
- Git commit: `36ed98b` (작업 트리에 이 PR의 변경 포함, `git_dirty=true`)
- 명령: `sleep-aware --input mock --actions mock --intention {sleep,wake}` 각 3회
- detector 설정: `ear_threshold=0.21`, `drowsy_seconds=2.0`, `recovery_seconds=0.5`, `source=mock`

| 의도 | run ID | 상태 sequence | action sequence | `run_end.status` | frame 수 | 이전 run과 일치 |
|---|---|---|---|---|---|---|
| sleep | `…Z-6bb4f386` | AWAKE → EYES_CLOSED → DROWSY → AWAKE → NO_FACE → AWAKE | `pause_media`, `light_off`, `start_session`, `end_session` (모두 성공) | completed | 195 | 기준 |
| sleep | `…Z-61b743e7` | 동일 | 동일 | completed | 195 | 일치 |
| sleep | `…Z-349794de` | 동일 | 동일 | completed | 195 | 일치 |
| wake | `…Z-69f5677a` | AWAKE → EYES_CLOSED → DROWSY → AWAKE → NO_FACE → AWAKE | `pause_media`, `light_on`, `buzzer_alert`, `play_media` (모두 성공) | completed | 195 | 기준 |
| wake | `…Z-10c1e43d` | 동일 | 동일 | completed | 195 | 일치 |
| wake | `…Z-21e85982` | 동일 | 동일 | completed | 195 | 일치 |

비교 기준은 detector 설정, 상태 sequence, action sequence와 성공 여부,
`run_end.status`, frame 수이다. run ID, wall time, latency는 실행마다 달라지므로
일치 기준에서 제외한다. run ID는 실행마다 서로 달라야 하며 위 6개 모두 다르다.

같은 비교를 `tests/test_mock_run_reproducibility.py`가 자동으로 수행하므로 CI에서
회귀를 감지한다. 이 결과는 mock 시나리오의 결정성만 보여 주며, 실제 얼굴·카메라
입력에 대한 재현성 근거는 아니다.

## Raspberry Pi HTTP 경로 (stub)

- 날짜: 2026-09-19
- 방법: `sleep_aware.adapters.PiStubServer`를 loopback(`127.0.0.1`)에서 실행하고
  실제 `RaspberryPiHttpActionExecutor`로 요청
- 검증 항목: 7개 endpoint 요청 경로와 `POST` 사용, 2xx 응답의 `succeeded`와
  `status_code`, 비2xx 응답의 `http_status`, 서비스 중지 시 `connection_error`,
  알 수 없는 endpoint의 404 처리, 반복 명령의 멱등 상태
- 폐루프 통합: `BaselinePipeline`이 stub을 상대로 Wake 시나리오를 실행해
  `pause_media → light_on → buzzer_alert → play_media` 순서와 최종 장치 상태 확인
- 결과: `tests/test_pi_stub_server.py` 7개 통과

stub은 HTTP 요청·응답 경로와 실패 처리만 검증한다. 조명, 부저, 미디어의 물리
동작과 Raspberry Pi 성능(RQ3)은 검증하지 않는다.
