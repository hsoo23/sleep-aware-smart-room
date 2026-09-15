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

모드가 바뀌거나 파이프라인이 다시 시작될 때 활성 Sleep session 또는 정책이 일시
정지한 media가 있으면 소유권을 즉시 버리지 않습니다. 다음 관찰에서 `END_SESSION`과
`PLAY_MEDIA` cleanup transition을 먼저 생성한 뒤 `IDLE`로 초기화합니다. 따라서 외부
상태가 정리되지 않은 채 내부 소유권만 사라지지 않으며, cleanup 이후에는 이전 실행의
에피소드 상태가 남지 않습니다.

각 `PipelineEvent.policy_transition`에는 관찰 상태, 전후 phase, 전이 사유와 action이
함께 기록됩니다. action 실행 실패와 무관하게 다음 프레임을 재관찰하며, 실행 결과는
기존 `action_results`에 별도로 남습니다.
