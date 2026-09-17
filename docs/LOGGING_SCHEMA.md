# Structured Run Log Schema

Schema version: **1.0** (`sleep_aware.eventlog.SCHEMA_VERSION`)

Baseline runs are logged as JSON Lines by `sleep_aware.eventlog.JsonlEventLogger`,
which implements the pipeline `EventLogger` contract. The machine-readable field
specification and validator live in `src/sleep_aware/eventlog/schema.py`; this
document describes their meaning. Any change to field names, types, or units must
bump `SCHEMA_VERSION` and update both files.

## Files, storage, and rotation

- One run writes one file: `<LOG_DIR>/<run_id>.jsonl`.
- `LOG_DIR` defaults to `results/logs`. Everything under `results/` is ignored by
  Git; keep the log directory there.
- `run_id` is `YYYYMMDDTHHMMSSZ-<8 hex>` (UTC start time plus random suffix), so
  files sort chronologically and never collide.
- The logger opens the file in exclusive-create mode and refuses to overwrite an
  existing run.
- The per-run file is the rotation unit. There is no size-based rotation inside a
  run: at 30 FPS a frame line is roughly 0.5 KB, about 50 MB per hour. Retention
  and archiving of old runs are manual.
- Each line is validated before writing and flushed immediately, so a crash keeps
  every completed frame readable. A file without a `run_end` line was interrupted.

## Clocks

| Purpose | Clock | Fields |
|---|---|---|
| Correlating a run with calendar time, experiment records, and other devices | Wall clock (`datetime.now(timezone.utc)`), ISO 8601 with UTC offset | `wall_time_utc` |
| Ordering frames and measuring every duration | Monotonic clock (`time.monotonic` by default) | `monotonic_timestamp_s`, all `*_latency_ms` |

Never compute durations from `wall_time_utc`; it can jump because of NTP or manual
clock changes. `monotonic_timestamp_s` has an arbitrary origin and is comparable
only within one run. `Frame.timestamp` and the `clock` given to
`BaselinePipeline` must come from the same monotonic clock.

## Record types

Every line contains these common fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | `"1.0"` |
| `record_type` | string | `run_start`, `frame`, or `run_end` |
| `run_id` | string | Identifier shared by all lines of the run |
| `wall_time_utc` | string | Wall-clock time when the line was written |

### `run_start` (first line)

| Field | Type | Description |
|---|---|---|
| `intention` | string | `sleep` or `wake` |
| `software_version` | string | `sleep_aware.__version__` |
| `git_commit` | string \| null | `git rev-parse HEAD`; null outside a Git checkout |
| `git_dirty` | bool \| null | Whether tracked files had uncommitted changes |
| `detector_name` | string | Ablation stage, e.g. `B0-fixed-ear` |
| `detector_version` | string | Detector implementation version |
| `config_version` | string | Identifier of the experiment configuration |
| `detector_config` | object | Experimental parameters only (thresholds, durations) |
| `python_version` | string | e.g. `3.11.9` |
| `platform` | string | OS and CPU architecture, e.g. `Linux-aarch64` |

### `frame` (one per processed frame)

| Field | Type | Description |
|---|---|---|
| `frame_sequence` | int | `Frame.sequence` from the frame source |
| `monotonic_timestamp_s` | number | Monotonic capture time of the frame |
| `intention` | string | `sleep` or `wake` |
| `ear` | number \| null | Mean EAR of both eyes; null when no face is found |
| `ear_threshold` | number \| null | Threshold the detector applied to this frame |
| `previous_state` | string \| null | State of the previous frame; null for the first frame |
| `state` | string | `NO_FACE`, `AWAKE`, `EYES_CLOSED`, or `DROWSY` |
| `state_changed` | bool | `previous_state != state`; true for the first frame |
| `actions` | array | Action results in execution order; empty when no action was requested |
| `inference_latency_ms` | number | Landmark extraction + EAR + detector update |
| `control_latency_ms` | number | Policy decision + execution of all actions |
| `end_to_end_latency_ms` | number | Frame capture to the last action result |

Each `actions` item:

| Field | Type | Description |
|---|---|---|
| `action` | string | `Action` value, e.g. `pause_media` |
| `success` | bool | Whether the executor reported success |
| `failure_reason` | string \| null | Redacted failure detail; null on success |
| `latency_ms` | number | Time spent in `ActionExecutor.execute` |

`end_to_end_latency_ms` includes time between capture and the start of processing
(queueing), so it can exceed `inference_latency_ms + control_latency_ms`. It
excludes writing the log line. Latencies are rounded to 0.001 ms.

### `run_end` (last line)

| Field | Type | Description |
|---|---|---|
| `status` | string | `completed`, or `failed` when the run raised |
| `frame_count` | int | Number of `frame` lines written |
| `error_type` | string \| null | Exception class name for failed runs; no message |

## Privacy

Logs must not contain video, images, landmarks, participant identity, email
addresses, IP addresses, URLs, hostnames, or machine-specific paths.

- Frame payloads and landmark coordinates are never written.
- `run_start` records only the explicit metadata above; service URLs, credentials,
  and hostnames from `Settings` are not included. Pass only experimental parameters
  in `detector_config`.
- `failure_reason` passes through `sleep_aware.eventlog.redact`, which replaces
  emails, URLs, IPv4/IPv6 addresses, `/Users/...`, `/home/...`, or Windows
  `C:\Users\...` paths, and local-network hostnames (`*.local`, `*.lan`, `*.home`,
  `*.internal`, `*.localdomain`) with `<email>`, `<url>`, `<ip>`, `<path>`, and
  `<host>`. User names containing spaces are masked through the next path separator,
  so part of the following message may also be masked, and a trailing dot on a
  hostname is included. Public domain names are kept so failure text stays readable.
- `run_end` stores only the exception class name, not its message.
- Link a run to a participant code in the experiment record
  (`docs/EXPERIMENT_LOG_TEMPLATE.md`), not in the log.

## Generating and validating a log

```bash
python -m sleep_aware.eventlog.mock_run            # writes results/logs/<run_id>.jsonl
python -m sleep_aware.eventlog.mock_run --intention sleep --log-dir results/logs
```

The mock run uses synthetic frames and a simulated clock; its latencies verify the
logging path and are not performance measurements.

```python
import json
from sleep_aware.eventlog import validate_record

with open(path, encoding="utf-8") as log:
    for line in log:
        validate_record(json.loads(line))  # raises ValueError on any violation
```
