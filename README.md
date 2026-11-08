# Sleep-Aware Smart Room

This repository extends the original *AI-Based Sleep-Aware Media and Smart Room Control System* toward an international journal study. The original prototype uses MediaPipe Face Mesh and a fixed eye aspect ratio (EAR) threshold to drive Sleep Aid and Wake-up actions. The proposed research contribution is the integrated system **if** its detection, generalization, robustness, edge performance, and intention-aware control are demonstrated quantitatively.

## Current status

| Area | Status | Evidence or remaining work |
|---|---|---|
| Phase 1 literature review | Approved | Research direction and RQ1–RQ6 approved as proposed contributions |
| Phase 2 software baseline | Implemented | Fixed-EAR CLI, closed-loop policy, mock/stub adapters, Pi action service, JSONL logging, and CI |
| Hardware-free tests | Available | Unit, mock pipeline, and HTTP stub tests; these do not validate physical devices |
| Development-host camera and Chrome | Limited checks recorded | See [camera results](docs/CAMERA_SMOKE_RESULTS.md); these are not Raspberry Pi results |
| Raspberry Pi relay, lamp, and buzzer | Reported operational by the team | The run command, device observations, and log still need to be recorded in the [physical-device checklist](docs/RASPBERRY_PI_SMOKE_TEST.md) |
| Full Sleep/Wake hardware loop | Team reports working functions; evidence pending | Record the observed actions, recovery, and device restoration for each mode |
| Raspberry Pi edge inference | Verification pending | Install camera/MediaPipe on Pi 4 and measure FPS, inference and end-to-end latency, CPU, and memory |
| Phase 3 detector | Planned | Adaptive EAR and PERCLOS modules exist but are not integrated or shown to improve the baseline; head pose remains planned |
| Phase 4 dataset and journal claims | Planned | Participant-disjoint protocol, ground truth, comparisons, and ablations remain |

The original code is preserved in [legacy/](legacy/README.md). Its web dashboard is a local static page in `legacy/index.html`; it calls the original `/set_config` and `/start_detection` APIs. The current CLI and Pi action service use different interfaces, so displaying the dashboard does **not** demonstrate the current baseline. Legacy runtime files remain unchanged for provenance.

## Research questions

| RQ | Focus |
|---|---|
| RQ1 | Adaptive EAR versus fixed EAR, including false detections |
| RQ2 | Generalization to unseen users |
| RQ3 | Lighting, face-angle, and camera-distance robustness |
| RQ4 | Real-time Raspberry Pi 4 inference and end-to-end latency |
| RQ5 | Accuracy, speed, CPU/memory, and computation trade-offs |
| RQ6 | Appropriateness of Sleep/Wake intention-aware control |

Every major experiment, table, and figure should address at least one RQ. See the [research plan](docs/RESEARCH_PLAN.md).

## Repository map

- `src/sleep_aware/capture/`: OpenCV camera and deterministic frame sources
- `src/sleep_aware/pipeline/`: landmark adapters, contracts, and baseline orchestration
- `src/sleep_aware/detection/`: EAR, temporal state, and preliminary adaptive/PERCLOS modules
- `src/sleep_aware/control/`: intention-aware closed-loop policy
- `src/sleep_aware/adapters/`: mock, Raspberry Pi HTTP, GPIO service, and host media control
- `src/sleep_aware/eventlog/`: structured JSONL events and run summary
- `docs/`: architecture, runbooks, verification evidence, and experiment templates
- `legacy/`: original submitted prototype, preserved for comparison
- `data/`, `results/`: Git-ignored experiment data and generated outputs
- `tests/`: automated unit and integration tests

## Installation and software checks

Use Python 3.10 or later. A development environment for hardware-free tests:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check src tests
python -m compileall -q src tests
python -m pytest -q
```

Copy `.env.example` to an untracked `.env` and set machine-specific values. Install `.[host]` on the camera/MediaPipe host and `.[raspberrypi]` on Raspberry Pi. The [baseline runbook](docs/BASELINE_RUNBOOK.md) gives the full setup. CI runs hardware-free checks only.

## Run the fixed-EAR baseline (B0)

Reproduce both software-only closed loops:

```bash
sleep-aware --input mock --actions mock --intention sleep
sleep-aware --input mock --actions mock --intention wake
```

Both use a deterministic state sequence and write JSONL logs under `results/logs/`. To use a camera after installing `.[host]`, first identify a usable camera:

```bash
python -m sleep_aware.capture.smoke --list
sleep-aware --input camera --actions mock --intention wake --no-display --max-frames 150
```

For the physical setup, run the Pi service and establish the SSH tunnel in the [Pi guide](docs/RASPBERRY_PI_SMOKE_TEST.md). On the macOS host, `--actions host` controls YouTube in Chrome and sends lamp/buzzer actions to the Pi:

```bash
sleep-aware --input camera --actions host --intention sleep --camera-index 0
sleep-aware --input camera --actions host --intention wake --camera-index 0
```

Select the verified camera index. Quit a displayed run with `q` or Escape. Use `--no-display --max-frames N` on a headless machine. The `--actions real` mode sends all actions to Pi HTTP; its media endpoints report success without physical media control. The Pi service alone executes actions and does not run AI inference.

| Action mode | Media | Lamp and buzzer | Session |
|---|---|---|---|
| `mock` | In-memory | In-memory | In-memory |
| `real` | Pi HTTP acknowledgement only | Pi HTTP / GPIO | Pi service memory |
| `host` | macOS Chrome | Pi HTTP / GPIO | Host memory |

A passing mock or HTTP stub run must not be reported as a hardware demonstration. Record physical results in the [demo validation form](docs/DEMO_VALIDATION.md).

On 2026-11-09, a team member reported that the functions worked after connecting
the Raspberry Pi. This is a user report, not an independently reviewed run
record: the command, device-by-device observations, and JSONL log have not yet
been supplied. It does not establish Pi-based AI inference or edge performance.

## Closed-loop design and ablation plan

```text
state detection -> intention-dependent actuation -> re-observation -> device restoration or policy transition
```

The [architecture](docs/ARCHITECTURE.md) distinguishes the current B0 implementation from the planned B1–B3 design. The [policy specification](docs/CLOSED_LOOP_POLICY.md) details state transitions and retries.

| Stage | Detector |
|---|---|
| B0 | Fixed EAR |
| B1 | Adaptive EAR |
| B2 | Adaptive EAR + PERCLOS |
| B3 | Adaptive EAR + PERCLOS + head pose |

## Privacy

Keep participant data, photos/videos, credentials, personal network addresses, and generated logs out of Git. See [SECURITY.md](SECURITY.md).
