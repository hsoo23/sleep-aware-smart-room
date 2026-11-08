# Research and Experiment Plan

## Approved research questions

| RQ | Question |
|---|---|
| RQ1 | Does adaptive EAR improve detection performance and reduce false detections relative to a fixed threshold? |
| RQ2 | Does the method generalize reliably to previously unseen users? |
| RQ3 | Is detection robust to changes in lighting, face angle, and camera distance? |
| RQ4 | Can the complete inference and control pipeline run in real time on Raspberry Pi 4 with low end-to-end latency? |
| RQ5 | What are the trade-offs among accuracy, speed, CPU and memory use, and computational cost? |
| RQ6 | Do Sleep/Wake intention-aware actions fit the situation better than a uniform response? |

## Approved contribution targets

1. Personal-baseline adaptive EAR threshold
2. Subject-independent / LOSO generalization
3. Robustness under lighting, camera distance, and face-angle variation
4. Raspberry Pi FPS, inference latency, CPU, memory, and end-to-end latency
5. Intention-aware closed-loop smart-room control

These are proposed contributions until supported quantitatively.

## Phase 2 - Stable baseline

- Preserve and reproduce the submitted fixed-EAR system.
- Separate input, detection, policy, IoT communication, devices, logging, and UI.
- Remove secrets and hard-coded environment values.
- Add repeatable setup instructions and automated unit tests.
- Record one complete Sleep Aid and one Wake-up demonstration.

## Phase 3 - Detection ablation sequence

Evaluate every stage independently:

1. Fixed EAR baseline
2. Adaptive EAR
3. Adaptive EAR + PERCLOS
4. Adaptive EAR + PERCLOS + head pose

Freeze development parameters before subject-independent testing.

## Phase 4 - Dataset protocol checklist

- Participants and consent procedure
- Normal, eyes-closed, and drowsy ground truth
- Sleep Aid and Wake-up scenarios
- Multiple illumination levels
- Camera positions and distances
- Face angles, natural movement, and appropriate partial occlusion
- Participant-disjoint train/test split or LOSO folds
- Date/participant/scenario/configuration naming for photos and video evidence

Do not mix frames from the same participant across training and testing when reporting user-independent performance.

## Required measurements

- Detection: accuracy, precision, recall, F1, false positives, false negatives
- Optional: confusion matrix, ROC curve, PR curve
- Edge: FPS, inference latency, CPU, memory, end-to-end response latency
- System: control success, recovery success, intention-action consistency

Every experiment, table, and figure must answer at least one approved research question.

The current fixed-EAR baseline and hardware-free tests do not establish improved
detection, unseen-user generalization, environmental robustness, or Raspberry Pi
edge performance. Those claims require the later experiments above.

