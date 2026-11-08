# Phase 3 Preparation: B1–B3 and Experimental Protocol

This document records implementation status and the next evidence required for RQ1–RQ5. It is an experiment plan, not a claim that detection accuracy or Raspberry Pi edge performance has improved.

## Detector stages and current status

| Stage | Configuration | Current status |
|---|---|---|
| B0 | Fixed EAR threshold, default 0.21 | Integrated and used in the 2026-11-05 physical demonstration |
| B1 | Personal median open-eye EAR × a frozen multiplier | Integrated into the CLI and hardware-free pipeline; real-camera pilot and labeled comparison pending |
| B2 | B1 + PERCLOS | `PerclosWindow` exists, but fusion and evaluation are not integrated |
| B3 | B2 + head pose | Planned; no head-pose module or evaluation yet |

## B1 guided calibration protocol

B1 collects the first `--calibration-samples` positive, finite EAR observations with a visible face (default 90). The operator must instruct the user to keep their eyes normally open and face the camera during this period. Missing faces do not count. The personal baseline is the median of those samples; the threshold is `baseline × --adaptive-multiplier` (default 0.75). The multiplier and protocol must be fixed using development participants before subject-independent evaluation.

Calibration frames have `ear_threshold=null` in JSONL and produce no actions. Their `AWAKE` state is a safe control placeholder, **not** a scored detection prediction. On the first visible frame after the required samples, the personal threshold is activated and remains fixed for that run. A run ending before activation records `run_end.status=failed` with a calibration-incomplete error. Starting another run resets calibration. The system cannot independently verify that the calibration samples are truly open-eye ground truth; document any protocol violation.

The B0 CLI remains the default. B1 can be exercised without the Pi:

```bash
sleep-aware --input mock --actions mock --detector b0 --intention wake
sleep-aware --input mock --actions mock --detector b1 --intention wake
sleep-aware --input mock --actions mock --detector b1 --intention sleep
```

After selecting a usable MacBook camera index and installing `.[host]`, run a supervised, device-free pilot:

```bash
sleep-aware --input camera --actions mock --detector b1 --intention wake --camera-index <verified-index> --no-display --max-frames 300
```

Keep eyes normally open through the initial calibration frames. The run should last long enough for calibration and the subsequent state sequence. Inspect `run_start.detector_name`, calibration parameters, the first non-null `ear_threshold`, state transitions, actions, and `run_end.status`. Do not interpret a successful mock action as a physical response.

## Initial software result and its limit

A deterministic synthetic check with open-eye EAR 0.30 and `multiplier=0.75` yielded B1 threshold 0.225 after 90 calibration frames. B0 used threshold 0.21. Both subsequent synthetic scenarios produced `AWAKE → EYES_CLOSED → DROWSY → AWAKE` and the intended Sleep/Wake action sequences. These are **pipeline and logging checks only**: the synthetic frames have no independent ground-truth labels for real people, and they do not establish fewer false detections or better accuracy.

## B0–B1 comparison needed for RQ1

1. Freeze the B0 and B1 parameter sets, camera configuration, and calibration instruction before evaluation.
2. Obtain consented, labeled sequences containing normal open eyes, eye closure, drowsiness, and recovery. Record frame-level or episode-level ground truth independently of the detector output.
3. Feed the **same frames and labels** to B0 and B1. The current live-camera CLI does not provide deterministic video replay; add a recorded-frame source or an offline EAR replay path before claiming a controlled head-to-head comparison.
4. Exclude B1 calibration frames (identified by `ear_threshold=null`) from scored predictions, and separate calibration data from evaluation data.
5. Report accuracy, precision, recall, F1, false positives, false negatives, confusion matrices, and per-participant results. Include confidence intervals or paired uncertainty estimates where the sample size permits.

A small supervised camera pilot can verify usability and logs before the formal dataset. It cannot answer RQ1 or RQ2 by itself.

## B2 and B3 preparation

For B2, define a PERCLOS window, closed-eye criterion, fusion rule, and missing-face behavior before testing. Use the existing `PerclosWindow` module only after wiring it into the same pipeline and adding tests for window boundaries, sparse frames, recovery, and event logging. Choose thresholds on development participants only.

For B3, implement head-pose estimation from face landmarks and document the coordinate convention, camera assumptions, pose thresholds, and failure behavior. Test with annotated changes in pitch and yaw, including conditions where face landmarks are missing. Compare B0→B1→B2→B3 on identical held-out data so each stage's incremental effect is interpretable.

## Participant and environment protocol: RQ2 and RQ3

Before full collection, define participant codes and consent, recruitment target, normal/closed/drowsy ground-truth rules, Sleep/Wake scenarios, lighting levels, camera distances, face angles, movement/occlusion conditions, and hardware configuration. Keep raw photos/videos and re-identification keys outside Git. Store date, participant code, scenario, and configuration in the private experiment record.

Use participant-disjoint training and test sets or leave-one-subject-out folds. Never randomly split frames from the same person across training and test while claiming unseen-user generalization. Tune B1/B2/B3 parameters on development participants and freeze them before held-out evaluation. Report per-participant as well as aggregate results, including difficult environmental conditions.

## Raspberry Pi 4 edge protocol: RQ4 and RQ5

The November 5 demonstration ran inference on the Mac and the action service on the Pi. Pi inference remains unmeasured. Once the kit is available, verify the Pi 4 OS/Python/MediaPipe installation, an attached camera, and a headless camera run. Measure B0 and B1 on the **same Pi, camera resolution, scene, and frame limit**; identify warm-up and B1 calibration frames separately. First use `--actions mock` to measure inference without network/device effects, then run a separate action-path trial for physical end-to-end latency.

Collect frame timestamps, FPS, inference latency, action-frame control latency, and end-to-end latency from JSONL. Collect CPU and memory for the same process and run using an external tool such as `pidstat`; JSONL does not contain those resource fields. Record mean/peak CPU and memory, median/p95 latencies, sample counts, tool versions, and failures. Do not compare Mac latency with Pi latency as if they were the same platform.

See [RASPBERRY_PI_SMOKE_TEST.md](RASPBERRY_PI_SMOKE_TEST.md) for installation and device checks, and [DEMO_VALIDATION.md](DEMO_VALIDATION.md) for the measurement record. Every later table or figure should identify the RQ it addresses.
