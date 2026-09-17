# Sleep-Aware Smart Room

Private research repository for a **real-time, personalized, intention-aware edge-AI drowsiness detection and closed-loop smart-room control system**.

The project extends the submitted *AI-Based Sleep-Aware Media and Smart Room Control System*. The original prototype uses MediaPipe Face Mesh and EAR to classify `AWAKE`, `EYES CLOSED`, and `DROWSY`, then applies different media/light/buzzer actions for Sleep Aid and Wake-up intentions.

## Research objective

The journal study evaluates the complete combination of:

- personal-baseline adaptive EAR detection;
- PERCLOS and head-pose feature improvements;
- subject-independent / LOSO generalization;
- robustness to illumination, distance, and face-angle variation;
- lightweight Raspberry Pi execution;
- intention-aware closed-loop IoT control.

The research value is the integrated system and quantitative validation, not EAR or MediaPipe alone.

## Current status

- **Phase 1:** literature review and research proposal approved
- **Phase 2:** code cleanup and reproducible fixed-EAR baseline in progress
- **Phase 3:** Adaptive EAR, PERCLOS, and head pose planned
- **Phase 4:** participant-disjoint dataset collection after the baseline is stable

## Repository layout

```text
.
├── src/sleep_aware/
│   ├── config.py
│   ├── capture/            # OpenCV and deterministic fake frame sources
│   ├── detection/          # EAR, adaptive calibration, PERCLOS, temporal state
│   ├── pipeline/           # Face Mesh adapter, contracts, fixed-EAR orchestration
│   ├── control/            # intention-aware closed-loop policy
│   └── eventlog/           # structured JSONL run logs and latency records
├── legacy/                 # original submitted working prototype (preserved verbatim)
├── config/                 # future versioned non-secret experiment configs
├── data/                   # raw/processed contents excluded from Git
├── results/                # generated experiment outputs excluded from Git
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CLOSED_LOOP_POLICY.md
│   ├── RESEARCH_PLAN.md
│   ├── LOGGING_SCHEMA.md
│   ├── DEMO_VALIDATION.md
│   └── EXPERIMENT_LOG_TEMPLATE.md
├── tests/
├── .env.example
└── pyproject.toml
```

## Quick start for the clean core

Python 3.10 or later is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

Install hardware/runtime extras only on the relevant machine:

```bash
# Host camera and detection
python -m pip install -e '.[host,server]'

# Raspberry Pi server
python -m pip install -e '.[server,raspberrypi]'
```

Copy `.env.example` to `.env` and set local values. Never commit `.env`.

## Reproducing the submitted baseline

The original prototype is preserved in `legacy/` and remains the behavioral reference while functionality is migrated into testable modules. The legacy system requires the original MacBook/Raspberry Pi hardware and software environment; it is not a hardware-free smoke test.

1. Start `legacy/pi_server.py` on Raspberry Pi.
2. Configure local URLs and launcher path from environment-specific values.
3. Start `legacy/launcher_server.py` on the host.
4. Open `legacy/index.html` and select Sleep Aid or Wake-up mode.
5. Confirm the full loop: detection -> action -> re-observation -> restoration/transition.

The legacy media controller currently depends on macOS, Google Chrome, AppleScript, and YouTube. Raspberry Pi GPIO functionality requires the physical relay and buzzer setup.

For a hardware-free verification of the migrated decision logic, run:

```bash
python -m compileall -q src tests
python -m pytest
```

The first command checks syntax and imports that do not require optional camera
or GPIO packages. The second command requires the development extra from the
Quick start section.

GitHub Actions runs Ruff and pytest on Python 3.10–3.13 for every pull request
without camera, MediaPipe, or GPIO packages. A passing CI run is not hardware
validation; see [docs/CONTINUOUS_INTEGRATION.md](docs/CONTINUOUS_INTEGRATION.md).

The in-memory device executor and Raspberry Pi HTTP adapter are documented in
[the Raspberry Pi smoke-test guide](docs/RASPBERRY_PI_SMOKE_TEST.md). Keep local
mock results separate from physical-device observations.

After installing the `host` extra, verify an attached webcam separately from CI:

```bash
python -m sleep_aware.capture.smoke
```

Camera index and requested resolution default to `CAMERA_INDEX`,
`CAMERA_WIDTH`, and `CAMERA_HEIGHT` from the environment. See
[docs/BASELINE_RUNBOOK.md](docs/BASELINE_RUNBOOK.md) for the manual result fields.

## Baseline CLI

하드웨어 없이 전체 폐루프와 구조화 로그를 재현하려면 다음 명령을 사용합니다.

```bash
sleep-aware --input mock --actions mock --intention sleep
sleep-aware --input mock --actions mock --intention wake
```

두 mock 실행은 고정된 `AWAKE → EYES_CLOSED → DROWSY → AWAKE` 시나리오를
사용하고, Sleep/Wake 의도별 동작과 run metadata·Git commit이 포함된 JSONL 로그를
`results/logs/`에 기록합니다. 실제 카메라와 Raspberry Pi HTTP 동작을 연결하려면
host extra와 환경 변수를 설정한 뒤 다음과 같이 실행합니다.

```bash
sleep-aware --input camera --actions real --intention wake --display
```

화면에서 `q` 또는 Escape를 누르면 카메라·MediaPipe·표시 창이 정리된 뒤 종료됩니다.
장치 없이 카메라 경로만 확인할 때는 `--actions mock`을 사용하고, 표시 창이 필요 없으면
`--no-display`를 지정합니다.

## Ablation plan

| Stage | Detector |
|---|---|
| B0 | Fixed EAR |
| B1 | Adaptive EAR |
| B2 | Adaptive EAR + PERCLOS |
| B3 | Adaptive EAR + PERCLOS + Head Pose |

See [docs/RESEARCH_PLAN.md](docs/RESEARCH_PLAN.md) for the experimental protocol and metrics.

## Closed-loop architecture

The system does not stop after an alert:

```text
state detection -> intention-dependent actuation -> re-observation -> restoration/policy transition
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the complete workflow and
[docs/CLOSED_LOOP_POLICY.md](docs/CLOSED_LOOP_POLICY.md) for the mode-specific
state transitions and action sequences.

## Privacy and secrets

Participant data, credentials, email app passwords, and local network details must not be committed. Review [SECURITY.md](SECURITY.md) before data collection.
