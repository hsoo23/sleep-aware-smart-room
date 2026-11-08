# Sleep/Wake Closed-Loop Policy

`ClosedLoopPolicy` is a device-independent state machine. It keeps two phases so a single `DROWSY` episode does not repeatedly trigger the same action sequence.

| Current phase | Observed state | Next phase | Sleep Aid actions | Wake-up actions |
|---|---|---|---|---|
| `IDLE` | `DROWSY` | `AWAITING_RECOVERY` | `PAUSE_MEDIA`, `LIGHT_OFF`, `START_SESSION` | `PAUSE_MEDIA`, `LIGHT_ON`, `BUZZER_ALERT` |
| `AWAITING_RECOVERY` | `DROWSY`, `EYES_CLOSED`, or `NO_FACE` | Remain | None | None |
| `AWAITING_RECOVERY` | `AWAKE` | `IDLE` | `END_SESSION` | `PLAY_MEDIA` |
| `IDLE` | `AWAKE`, `EYES_CLOSED`, or `NO_FACE` | Remain | None | None |

The temporal detector emits `AWAKE` only after eyes have stayed open for `recovery_seconds`; the policy accepts that state as recovery. `NO_FACE` is neither recovery nor a new episode. Following an action, the pipeline observes the next frame before deciding whether to restore or transition.

If the mode changes or the pipeline resets while a Sleep session or paused media is owned by the policy, it first schedules `END_SESSION` or `PLAY_MEDIA` cleanup on the next observation, then returns to `IDLE`. `PipelineEvent.policy_transition` records the observed state, old/new phases, reason, and requested actions. Action outcomes are recorded separately in `action_results`.

## Acknowledgement and retries

`BaselinePipeline` returns action outcomes to `ClosedLoopPolicy.acknowledge()`. Only failed actions are scheduled again on the next observation. If there is no new state-transition action, the reason is `ACTION_RETRY`; otherwise retries are prepended to new actions. A failed buzzer does not prevent later `PLAY_MEDIA` or `END_SESSION` recovery.

- Episode actions (`PAUSE_MEDIA`, `LIGHT_OFF`, `LIGHT_ON`, `BUZZER_ALERT`, `START_SESSION`) are retried up to `max_action_retries` (default 2) while the same episode remains active. Recovery, reset, or mode change discards their remaining retries.
- Cleanup actions (`END_SESSION`, `PLAY_MEDIA`) remain pending until successful. A new `PAUSE_MEDIA` supersedes an old `PLAY_MEDIA` retry; media resumes on the new episode's recovery.
- If a prior `END_SESSION` retry remains when a new Sleep episode starts, the policy continues the existing session rather than sending `START_SESSION` that might immediately be undone by the pending end. The session ends once on the new episode's recovery.
- `reset()` discards failed episode-action retries but retains cleanup retries and owned-resource state. `has_pending_cleanup` exposes that outstanding work.

`BaselinePipeline.close()` attempts cleanup within its retry limit. If cleanup remains, a later `run()` retries it before accepting new observations and raises `RuntimeError` if it still fails. Each run resets prior state history and the detector's temporal state. The CLI reports an incomplete cleanup as a failure even after Ctrl+C or a pipeline error so the operator can inspect the external devices.
