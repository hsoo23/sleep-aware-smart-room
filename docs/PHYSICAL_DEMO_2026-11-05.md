# Physical Demonstration Record: 2026-11-05

This is an English, privacy-conscious summary of the evidence archive prepared on 2026-11-09. The physical demonstration took place on **2026-11-05 (KST)**. The original ZIP and JSONL files are retained outside the public Git repository.

## Provenance and execution boundary

- Source archive: `demo-evidence-2026-11-05.zip`; SHA-256 `fa38bca5964806edf265d34802b473d097b3d6836768b29df6c2e227b9b37df0`.
- All 12 JSONL `run_start` records identify `main` commit `69d02641cfaeca0e8785c1b3463b2b68561866d1` and `git_dirty=false`. This is the **demonstration commit**, not the current documentation commit.
- The archive README reports a Mac running camera inference and Chrome/YouTube control, and a Raspberry Pi 4 Model B Rev 1.5 running Debian 13, Python 3.13.5, `RPi.GPIO` 0.7.1, and the action service. It reports a relay on GPIO17 (physical pin 11), a buzzer on GPIO18 (physical pin 12), a USB lamp powered from a Pi USB port, and an SSH tunnel to the Pi service on `127.0.0.1:5050`.
- In the representative runs, `source=camera`, `action_mode=host`, fixed EAR threshold `0.21`, `drowsy_seconds=2.0`, and `recovery_seconds=0.5`. **AI inference ran on the Mac; the Pi ran the action service.**
- A separate `sleep-aware-web.py` launcher in the archive started the repository's `sleep_aware.cli --actions host` process and supported the web demonstration. This launcher and its `iotWebInterface` page are **not** part of the repository's `main` branch. The preserved `legacy/index.html` does not directly call the current CLI.

## What was observed

| Item | Human observation or report | What the JSONL establishes |
|---|---|---|
| Lamp HTTP control | The team reports that direct Mac-to-Pi POST requests switched the real lamp off and on. | These direct requests are not in the camera JSONL. |
| Sleep Aid | The user observed YouTube pause and the lamp turn off after closed eyes. | The representative camera/host run records `DROWSY` followed by successful `pause_media`, `light_off`, and `start_session`; later `AWAKE` records successful `end_session`. |
| Wake-up | The team reports that the Wake-up functions operated normally. | The representative camera/host run records successful `pause_media`, `light_on`, and `buzzer_alert` after `DROWSY`, followed by `play_media` after `AWAKE`. |
| Email report | After the archive was prepared, the user separately reported actual email receipt. The receipt date and message artifact were not supplied. | Email transport and receipt are not recorded in the JSONL. The archive's separate web launcher contains SMTP/report-sending code; the current core CLI and Pi action service do not record email delivery. |

An `action.success=true` entry means that the action executor returned success; it is not an independent measurement of lamp state, buzzer sound, Chrome playback, or email delivery. The physical observations above come from the team report. The archive contains no video of the individual physical actions and no GPIO voltage/current measurement.

The Sleep policy ends the session on recovery. It does not automatically turn the lamp back on or resume YouTube in Sleep Aid mode; those are not claimed as Sleep recovery actions.

## Representative complete runs

| Mode | KST interval | Frames | Recorded action sequence | End status |
|---|---|---:|---|---|
| Sleep Aid | 23:14:54–23:16:24 | 2,603 | `pause_media → light_off → start_session → end_session`, twice; all executor results successful | `completed` |
| Wake-up | 23:18:21–23:18:56 | 925 | `pause_media → light_on → buzzer_alert → play_media`, twice; all executor results successful | `completed` |

The corresponding run IDs are `20261105T141454Z-f0617b73` (Sleep) and `20261105T141821Z-b3cd0c31` (Wake). The archive's `representative-events.json` identifies the action frames and KST times. The source archive README contains the Pi service, SSH tunnel, CLI, and external web-launcher commands. JSONL does not record the complete shell command or actual camera index; an index shown in the archive's example command must not be treated as the verified demonstration index.

## Inventory of all JSONL runs

The 12 original logs passed the repository's JSONL schema validator, and each file's SHA-256 matched `log-summary.json`. Nine have `run_end.status=completed`. Three have `run_end.status=failed` with `error_type=KeyboardInterrupt`; their successful action events can be examined separately, but they are not counted as normally completed runs. Three of the completed runs contain no action events and do not demonstrate device actuation.

| Run ID suffix | Intention | Action mode | Frames | Action results | `run_end.status` |
|---|---|---|---:|---:|---|
| `fd1dc9f5` | Sleep | `real` | 882 | 4 | `completed` |
| `40ae8a07` | Sleep | `host` | 361 | 4 | `completed` |
| `5ac649a1` | Sleep | `host` | 1,270 | 4 | `completed` |
| `00c898de` | Sleep | `host` | 185 | 0 | `completed` |
| `bff03c13` | Sleep | `host` | 208 | 0 | `completed` |
| `058eeebd` | Sleep | `host` | 5,473 | 24 | `failed` (`KeyboardInterrupt`) |
| `afce8e03` | Wake | `host` | 819 | 8 | `failed` (`KeyboardInterrupt`) |
| `22194586` | Sleep | `host` | 1,014 | 4 | `completed` |
| `223abc91` | Sleep | `host` | 434 | 0 | `completed` |
| `f0617b73` | Sleep | `host` | 2,603 | 8 | `completed` |
| `7e61b903` | Wake | `host` | 889 | 12 | `failed` (`KeyboardInterrupt`) |
| `b3cd0c31` | Wake | `host` | 925 | 8 | `completed` |

The single `--actions real` run cannot establish physical media control because the Pi media endpoint only acknowledges that action. The representative physical demonstrations used `--actions host`.

## Research interpretation

The demonstration supplies preliminary **functional evidence for RQ6**: the two intentions produced different action sequences and recovery behavior in camera/host runs, with physical effects reported by the team. It does not quantify intention-action appropriateness against a uniform-response baseline. It provides **no Raspberry Pi inference benchmark for RQ4 or trade-off analysis for RQ5**: FPS and inference latency in these logs are Mac-host measurements; Pi CPU and memory were not captured. It also does not answer RQ1–RQ3 on adaptive detection, unseen users, or environmental robustness.

The public repository contains only this derived summary. Keep the source ZIP, JSONL, web launcher, any email evidence, and participant media in controlled storage and share them separately when appropriate.
