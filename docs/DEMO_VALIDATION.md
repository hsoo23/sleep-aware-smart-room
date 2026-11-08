# Phase 2 Demonstration and Verification Record

Use this form for future demonstrations. Check a box only after observing that item in the named environment. Enter `Not performed` instead of leaving an unperformed measurement ambiguous. Keep software-only, host-only, and physical-device results separate.

## Recorded physical demonstration

The [2026-11-05 demonstration record](PHYSICAL_DEMO_2026-11-05.md) now identifies
the run date, Git commit, 12 validated JSONL files, representative Sleep/Wake
action and recovery sequences, and the team's physical observations. It also
distinguishes the subsequently reported email receipt from the core JSONL.
The original shell command and camera index are not recorded in JSONL, and
face inference ran on the Mac rather than on the Pi. The unchecked items below
remain a template for future runs and additional measurements.

## Pre-submission checklist

### Automated and mock checks

- [ ] `python -m pytest -q` passes on the cited Git commit.
- [ ] `ruff check src tests` passes.
- [ ] Sleep mock log contains the state sequence, Sleep actions, and a completed `run_end`.
- [ ] Wake mock log contains the state sequence, Wake actions, and a completed `run_end`.
- [ ] JSONL includes run ID, configuration, Git commit, states, action results, and latencies.

### Camera, host, and Raspberry Pi observations

- [ ] Camera permission and actual frame acquisition confirmed; `python -m sleep_aware.capture.smoke --list` identifies a usable index without a black-frame warning.
- [ ] Face present, eyes closed, drowsy, and no face are distinguishable in the display and log.
- [ ] Chrome permits JavaScript from Apple Events and an actual YouTube video tab is open.
- [ ] Sleep Aid: media pauses, lamp turns off, session starts, later re-observation leads to session end.
- [ ] Wake-up: media pauses, lamp stays on, buzzer sounds, later re-observation leads to media playback.
- [ ] Pi HTTP failures are distinguishable: `timeout`, `connection_error`, `request_error`, and `http_status`. Record observed cases only.
- [ ] `q`/Escape and error exits leave the camera, MediaPipe processor, and owned device resources in the expected state.
- [ ] No participant media, credentials, private IPs, or machine-specific paths appear in the repository or shared logs.

## Run record

| Field | Value |
|---|---|
| Date and time | |
| Operator | |
| Git commit and dirty state | |
| Command | |
| Intention (Sleep/Wake) | |
| OS and Python version | |
| Camera device/index (built-in, Continuity, USB, or CSI) | |
| Camera resolution and measured FPS | |
| Raspberry Pi model/OS, relay, and buzzer identifiers | |
| JSONL log path | |
| Pi FPS (if inference ran on Pi) | |
| Pi CPU use, mean and peak | |
| Pi memory use, mean and peak | |
| Inference latency, median and p95 (ms) | |
| Control latency on action frames, median and p95 (ms) | |
| End-to-end latency, median and p95 (ms) | |
| Performance tool and separate result file | |
| Observed state transitions | |
| Observed actions and recovery | |
| Failures or anomalies | |
| Private location of evidence video/screenshots | |

The JSONL provides frame-based latency but not CPU or memory. Measure CPU and memory separately on the same Pi run, and identify the process and sampling method. Do not place development-host values into Pi fields. A physical result needs an observed device response, not just a successful HTTP status.

## Research-question traceability

| RQ | Approved question | Phase 2 evidence available or needed | Later evidence |
|---|---|---|---|
| RQ1 | Does Adaptive EAR outperform fixed EAR and reduce false detections? | B0 fixed-EAR trace only; no comparative performance claim | B0/B1 comparison with ground truth and false-positive/negative counts |
| RQ2 | Does detection generalize to unseen users? | Not assessed in Phase 2 | Participant-disjoint or LOSO evaluation |
| RQ3 | Is detection robust to lighting, angle, and distance changes? | Not assessed in Phase 2 | Controlled and realistic condition tests |
| RQ4 | Can Pi 4 inference and control run in real time with low latency? | Pi 4 action service was used in the November 5 demonstration; inference ran on the Mac | Repeated Pi FPS, inference, and end-to-end measurements |
| RQ5 | What are the accuracy/resource trade-offs? | No cross-detector comparison yet | B0–B3 accuracy, FPS, CPU, memory, and computational cost |
| RQ6 | Are intention-aware actions more appropriate than a uniform response? | November 5 Sleep/Wake camera/host logs show different action and recovery sequences, with physical effects reported by the team | Quantified comparison with a uniform-response baseline, control success, and recovery |

Three identical mock traces show deterministic execution, not RQ1 accuracy improvement. Development-host camera and Chrome observations are documented in [CAMERA_SMOKE_RESULTS.md](CAMERA_SMOKE_RESULTS.md); mock/stub results in [HARDWARE_FREE_RESULTS.md](HARDWARE_FREE_RESULTS.md). Neither is Pi edge evidence. Link every eventual paper table, figure, and video to at least one approved RQ.
