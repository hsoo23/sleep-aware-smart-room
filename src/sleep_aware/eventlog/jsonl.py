"""Append-only JSONL implementation of the pipeline ``EventLogger`` contract."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import IO, Any

from sleep_aware.pipeline import PipelineEvent

from .metadata import RunMetadata
from .privacy import redact
from .schema import SCHEMA_VERSION, validate_record

WallClock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ms(seconds: float | None) -> float:
    return 0.0 if seconds is None else round(seconds * 1000.0, 3)


class JsonlEventLogger:
    """Write one run to ``<log_dir>/<run_id>.jsonl``.

    The file holds a ``run_start`` record, one ``frame`` record per pipeline
    event, and a ``run_end`` record written by ``close``. Each run gets its own
    file, which is the rotation unit; an existing file is never overwritten.
    Every line is validated before it is written and flushed immediately so a
    crash leaves all completed frames readable.
    """

    def __init__(
        self,
        log_dir: Path | str,
        metadata: RunMetadata,
        *,
        wall_clock: WallClock = _utc_now,
    ) -> None:
        self._metadata = metadata
        self._wall_clock = wall_clock
        self._frame_count = 0
        self.path = Path(log_dir) / f"{metadata.run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file: IO[str] | None = self.path.open("x", encoding="utf-8")
        self._write(
            {
                **self._common("run_start"),
                "intention": metadata.intention.value,
                "software_version": metadata.software_version,
                "git_commit": metadata.git_commit,
                "git_dirty": metadata.git_dirty,
                "detector_name": metadata.detector_name,
                "detector_version": metadata.detector_version,
                "config_version": metadata.config_version,
                "detector_config": dict(metadata.detector_config),
                "python_version": metadata.python_version,
                "platform": metadata.platform,
            }
        )

    def log(self, event: PipelineEvent) -> None:
        self._write(
            {
                **self._common("frame"),
                "frame_sequence": event.frame_sequence,
                "monotonic_timestamp_s": event.timestamp,
                "intention": event.intention.value,
                "ear": event.ear,
                "ear_threshold": event.ear_threshold,
                "previous_state": (
                    event.previous_state.value if event.previous_state is not None else None
                ),
                "state": event.state.value,
                "state_changed": event.state_changed,
                "actions": [
                    {
                        "action": result.action.value,
                        "success": result.succeeded,
                        "failure_reason": (
                            None
                            if result.succeeded
                            else redact(result.detail or "unspecified failure")
                        ),
                        "latency_ms": _ms(result.latency),
                    }
                    for result in event.action_results
                ],
                "inference_latency_ms": _ms(event.latency.inference),
                "control_latency_ms": _ms(event.latency.control),
                "end_to_end_latency_ms": _ms(event.latency.end_to_end),
            }
        )
        self._frame_count += 1

    def close(self, error: BaseException | None = None) -> None:
        """Write ``run_end`` and close the file; repeated calls are ignored."""
        if self._file is None:
            return
        try:
            self._write(
                {
                    **self._common("run_end"),
                    "status": "completed" if error is None else "failed",
                    "frame_count": self._frame_count,
                    "error_type": type(error).__name__ if error is not None else None,
                }
            )
        finally:
            self._file.close()
            self._file = None

    def __enter__(self) -> JsonlEventLogger:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close(exc)

    def _common(self, record_type: str) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "record_type": record_type,
            "run_id": self._metadata.run_id,
            "wall_time_utc": self._wall_clock().astimezone(timezone.utc).isoformat(),
        }

    def _write(self, record: dict[str, Any]) -> None:
        if self._file is None:
            raise RuntimeError("event log is closed")
        validate_record(record)
        self._file.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        self._file.flush()
