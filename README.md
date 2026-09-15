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
│   ├── detection/          # EAR, adaptive calibration, PERCLOS, temporal state
│   └── control/            # intention-aware closed-loop policy
├── legacy/                 # original submitted working prototype (preserved verbatim)
├── config/                 # future versioned non-secret experiment configs
├── data/                   # raw/processed contents excluded from Git
├── results/                # generated experiment outputs excluded from Git
├── docs/
│   ├── ARCHITECTURE.md
│   ├── RESEARCH_PLAN.md
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

The in-memory device executor and Raspberry Pi HTTP adapter are documented in
[the Raspberry Pi smoke-test guide](docs/RASPBERRY_PI_SMOKE_TEST.md). Keep local
mock results separate from physical-device observations.

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

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the complete workflow.

## Privacy and secrets

Participant data, credentials, email app passwords, and local network details must not be committed. Review [SECURITY.md](SECURITY.md) before data collection.
