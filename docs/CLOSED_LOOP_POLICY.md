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

## 실행 결과 확인과 재시도

`BaselinePipeline`은 실행 결과를 `ClosedLoopPolicy.acknowledge()`로 정책에 돌려줍니다.
실패한 action만 다음 관찰에서 다시 생성됩니다. 새 관찰이 만든 action이 없으면 전이
사유는 `ACTION_RETRY`이고, 새 action이 있으면 재시도 action을 앞에 붙여 함께 실행합니다.
재시도는 이후 전이를 막지 않으므로 부저 같은 장치가 계속 실패해도 회복 시
`PLAY_MEDIA`·`END_SESSION`은 정상적으로 생성됩니다.

- 에피소드 action(`PAUSE_MEDIA`, `LIGHT_OFF`, `LIGHT_ON`, `BUZZER_ALERT`,
  `START_SESSION`)은 같은 에피소드가 `AWAITING_RECOVERY`로 유지되는 동안에만
  `max_action_retries`(기본 2회)까지 재시도하고, 회복·reset·모드 변경 시 버립니다.
  오프라인 장치의 timeout이 매 프레임 반복되지 않게 하기 위한 제한입니다.
- cleanup action(`END_SESSION`, `PLAY_MEDIA`)은 성공할 때까지 유지합니다. 단, 새
  에피소드가 `PAUSE_MEDIA`를 실행하면 이전 `PLAY_MEDIA` 재시도는 의미가 없으므로 버리고,
  새 에피소드의 회복 시점에 다시 재생합니다.
- `END_SESSION` 재시도가 남은 상태에서 새 Sleep 에피소드가 시작되면 `START_SESSION`을
  보내지 않고 이전 세션을 이어 갑니다. 재시도한 `END_SESSION`이 새 세션을 잘못 종료하는
  순서 문제를 막고, 세션은 새 에피소드의 회복 시점에 한 번 종료됩니다. 정리 재시도 때문에
  Sleep/Wake 동작 자체를 보류하지는 않습니다.

`reset()`은 에피소드 중 실패한 action(`LIGHT_ON`, `BUZZER_ALERT` 등)의 재시도는
버리지만, 소유 자원을 해제하는 cleanup action(`END_SESSION`, `PLAY_MEDIA`)의 재시도는
유지합니다. `ClosedLoopPolicy.has_pending_cleanup`은 이런 미완료 cleanup이나 아직
해제하지 않은 소유권이 남아 있는지 알려 줍니다.

`BaselinePipeline.close()`가 재시도 한도 안에 cleanup을 끝내지 못하면, 다음 `run()`은
시작 전에 남은 cleanup을 다시 시도합니다. 그래도 실패하면 `RuntimeError`로 새 실행을
거부하므로 외부 장치 상태가 정리되지 않은 채 다음 실행이 시작되지 않습니다. `run()`은
매 실행마다 이전 실행의 검출 상태 기록과 `DrowsinessDetector.reset()`으로 검출기의 시간
기록도 초기화합니다. CLI 카메라 실행과 mock 실행은
종료 시 cleanup이 끝나지 않았으면 Ctrl+C나 실행 오류로 끝난 경우에도 실패로 보고해 장치
상태를 직접 확인하도록 안내합니다.
