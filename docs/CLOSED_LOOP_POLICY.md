# Sleep/Wake 폐루프 상태 정책

`ClosedLoopPolicy`는 장치와 분리된 순수 정책입니다. 한 번의 `DROWSY` 에피소드에서
동일한 action sequence가 반복되지 않도록 다음 두 phase만 유지합니다.

| 현재 phase | 관찰 상태 | 다음 phase | Sleep Aid action | Wake-up action |
| --- | --- | --- | --- | --- |
| `IDLE` | `DROWSY` | `AWAITING_RECOVERY` | `PAUSE_MEDIA`, `LIGHT_OFF`, `START_SESSION` | `PAUSE_MEDIA`, `LIGHT_ON`, `BUZZER_ALERT` |
| `AWAITING_RECOVERY` | `DROWSY` | 유지 | 없음 | 없음 |
| `AWAITING_RECOVERY` | `EYES_CLOSED` | 유지 | 없음 | 없음 |
| `AWAITING_RECOVERY` | `NO_FACE` | 유지 | 없음 | 없음 |
| `AWAITING_RECOVERY` | `AWAKE` | `IDLE` | `END_SESSION` | `PLAY_MEDIA` |
| `IDLE` | `AWAKE`, `EYES_CLOSED`, `NO_FACE` | 유지 | 없음 | 없음 |

`AWAKE`는 `TemporalDrowsinessDetector.recovery_seconds` 동안 눈 뜬 상태가 이어진
후에만 발생하므로, 정책은 이 상태만 회복으로 인정합니다. 얼굴이 사라진 `NO_FACE`는
회복도 새 에피소드도 아니며 기존 `AWAITING_RECOVERY` phase를 유지합니다.

모드가 바뀌면 이전 모드가 소유하던 에피소드, Sleep session, media pause 상태를 모두
폐기합니다. 따라서 새 모드의 첫 `AWAKE`가 이전 모드의 `END_SESSION` 또는
`PLAY_MEDIA`를 발생시키지 않습니다. 파이프라인은 `run()` 시작 시에도 같은 reset을
수행하므로 재시작 이전의 내부 상태가 다음 실행으로 넘어가지 않습니다.

각 `PipelineEvent.policy_transition`에는 관찰 상태, 전후 phase, 전이 사유와 action이
함께 기록됩니다. action 실행 실패와 무관하게 다음 프레임을 재관찰하며, 실행 결과는
기존 `action_results`에 별도로 남습니다.
