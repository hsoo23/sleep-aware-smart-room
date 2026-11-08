# Hardware-Free Verification Results

This record covers checks performed without a physical camera, Raspberry Pi, relay, or buzzer. Physical observations are summarized in [PHYSICAL_DEMO_2026-11-05.md](PHYSICAL_DEMO_2026-11-05.md), with a reusable form in [DEMO_VALIDATION.md](DEMO_VALIDATION.md); development-host camera observations are in [CAMERA_SMOKE_RESULTS.md](CAMERA_SMOKE_RESULTS.md). The results below do not establish detection accuracy, Raspberry Pi edge performance, or physical-device operation.

## Deterministic mock reproducibility

- Date: 2026-09-19
- Git base: `36ed98b` with changes in the then-current worktree (`git_dirty=true`)
- Commands: `sleep-aware --input mock --actions mock --intention sleep` and `--intention wake`, each run three times
- Detector configuration: `ear_threshold=0.21`, `drowsy_seconds=2.0`, `recovery_seconds=0.5`, `source=mock`
- Result: all six runs completed with 195 frames each. Within each intention, detector configuration, state sequence, action sequence, action success, and `run_end.status` matched across the three runs.

| Intention | Run suffixes | State sequence | Action sequence |
|---|---|---|---|
| Sleep | `…Z-6bb4f386`, `…Z-61b743e7`, `…Z-349794de` | `AWAKE → EYES_CLOSED → DROWSY → AWAKE → NO_FACE → AWAKE` | `pause_media → light_off → start_session → end_session`, all successful |
| Wake | `…Z-69f5677a`, `…Z-10c1e43d`, `…Z-21e85982` | Same sequence | `pause_media → light_on → buzzer_alert → play_media`, all successful |

Run IDs were distinct as expected. Wall time and latency are not expected to match exactly between runs. `tests/test_mock_run_reproducibility.py` repeats the relevant comparison in CI. This proves deterministic mock behavior only; it does not measure fixed-EAR accuracy on real people or answer RQ1's adaptive-versus-fixed comparison.

## Raspberry Pi HTTP route with a stub

- Date: 2026-09-19
- Method: run `sleep_aware.adapters.PiStubServer` on `127.0.0.1` and issue requests through the real `RaspberryPiHttpActionExecutor`.
- Verified: all seven endpoint paths and `POST`; 2xx success and status codes; non-2xx `http_status`; `connection_error` after stopping the service; unknown-endpoint 404; repeated-command state.
- Closed-loop integration: `BaselinePipeline` ran the Wake scenario against the stub and produced `pause_media → light_on → buzzer_alert → play_media` with the expected final mock device state.
- Recorded automated result at the time: seven `tests/test_pi_stub_server.py` tests passed.

The stub validates the HTTP request/response path and failure handling. It does not validate physical lamp, buzzer, or media action, and it provides no Raspberry Pi RQ4/RQ5 measurements.
