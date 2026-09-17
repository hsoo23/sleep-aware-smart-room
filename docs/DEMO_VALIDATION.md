# Phase 2 시연 및 검증 기록

## 제출 전 체크리스트

### 자동 검증

- [ ] `pytest -q`가 통과한다.
- [ ] `ruff check src tests`가 통과한다.
- [ ] Sleep mock 로그에 전체 상태 전이와 Sleep action sequence가 있다.
- [ ] Wake mock 로그에 전체 상태 전이와 Wake action sequence가 있다.
- [ ] 로그에 run ID, 설정, Git commit, 상태, 동작 결과, latency가 있다.

### 실제 장치 검증

- [ ] 카메라 권한과 실제 frame 획득을 확인했다.
- [ ] 얼굴 있음, 눈 감김, 얼굴 없음이 화면과 로그에서 구분된다.
- [ ] Sleep: 미디어 일시정지, 조명 끄기, 세션 시작·종료를 확인했다.
- [ ] Wake: 미디어 일시정지, 조명 켜기, 부저, 미디어 재생을 확인했다.
- [ ] Raspberry Pi HTTP 실패가 timeout 또는 상태 코드로 기록된다.
- [ ] `q`/Escape와 예외 종료 뒤 카메라·MediaPipe·장치가 안전 상태다.
- [ ] 참가자 영상, 이메일, IP, 로컬 경로가 저장소와 공유 로그에 없다.

## 실행 기록 양식

| 항목 | 기록 |
|---|---|
| 날짜·시간 | |
| 담당자 | |
| Git commit | |
| 실행 명령 | |
| 의도(Sleep/Wake) | |
| OS·Python | |
| 카메라·해상도·FPS | |
| Raspberry Pi·relay·buzzer | |
| JSONL 로그 경로 | |
| 상태 전이 결과 | |
| action 및 복구 결과 | |
| 실패·이상 현상 | |
| 증거 영상/스크린샷의 비공개 보관 위치 | |

실제 장치 검증을 수행하지 않았다면 빈칸 대신 `미실시`라고 기록합니다. mock 결과와
하드웨어 결과는 같은 칸에 섞지 않습니다.

## 연구 질문 추적표

| RQ | 질문 | Phase 2에서 확보하는 증거 | 후속 단계 |
|---|---|---|---|
| RQ1 | Fixed EAR baseline이 상태를 재현 가능하게 판정하는가? | 상태 순서, threshold·지속시간 설정, frame별 EAR·latency 로그 | Phase 3 detector ablation과 비교 |
| RQ2 | 사용자 의도에 따라 적절한 폐루프 동작과 복구가 실행되는가? | Sleep/Wake action sequence, 성공 여부, 재관찰 후 복구 로그 | 실제 장치 반복 성공률 보고 |
| RQ3 | edge 환경에서 실시간 실행 가능한가? | Raspberry Pi에서 측정한 FPS, CPU, memory, inference/control/end-to-end latency. 측정하지 않은 항목은 `미실시`로 기록 | 장시간 실행과 detector별 비용 비교 |
| RQ4 | 조명·거리·각도 및 사용자 차이에 강건한가? | Phase 2에서는 측정하지 않음 | Phase 3~4 robustness 및 LOSO 실험 |

개발 호스트의 카메라 smoke 결과는 카메라 획득 점검일 뿐이며 RQ3의 edge 실행 가능성
근거로 사용하지 않습니다. 개발 호스트에서 측정한 latency도 edge 결과와 분리해 기록합니다.

Phase 3 계획 항목을 Phase 2의 검증 결과로 표기하지 않습니다. 논문 표·그림·영상은 위
RQ 중 하나와 연결하고, 연결되지 않는 결과는 핵심 실험 근거로 사용하지 않습니다.
