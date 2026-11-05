"""Summarize one JSONL run log into the figures the validation record asks for.

``python -m sleep_aware.eventlog.summary results/logs/<run_id>.jsonl``

Frames without actions have a near-zero control latency, so a median over every frame
hides the device cost. Control and end-to-end figures are therefore also reported for
frames that executed an action. CPU and memory are not in the log; see
``docs/RASPBERRY_PI_SMOKE_TEST.md``.
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

from sleep_aware.eventlog.schema import validate_record


@dataclass(frozen=True)
class LatencyStats:
    count: int
    median_ms: float
    p95_ms: float


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    platform: str
    action_mode: str | None
    status: str
    frame_count: int
    fps: float | None
    inference: LatencyStats | None
    control: LatencyStats | None
    end_to_end: LatencyStats | None
    control_with_actions: LatencyStats | None
    end_to_end_with_actions: LatencyStats | None
    states: tuple[str, ...]
    actions: tuple[tuple[str, bool, str | None], ...]


def _stats(values: Sequence[float]) -> LatencyStats | None:
    """Return the median and the nearest-rank p95, or ``None`` without samples."""
    if not values:
        return None
    ordered = sorted(values)
    rank = math.ceil(0.95 * len(ordered))
    return LatencyStats(len(ordered), median(ordered), ordered[rank - 1])


def summarize(records: Iterable[dict[str, Any]]) -> RunSummary:
    """Build a summary, validating every record; a log without ``run_end`` is interrupted."""
    start: dict[str, Any] | None = None
    end: dict[str, Any] | None = None
    frames: list[dict[str, Any]] = []
    for record in records:
        validate_record(record)
        if record["record_type"] == "run_start":
            start = record
        elif record["record_type"] == "run_end":
            end = record
        else:
            frames.append(record)
    if start is None:
        raise ValueError("log has no run_start record")

    timestamps = [frame["monotonic_timestamp_s"] for frame in frames]
    elapsed = timestamps[-1] - timestamps[0] if timestamps else 0.0
    with_actions = [frame for frame in frames if frame["actions"]]

    def values(items: list[dict[str, Any]], name: str) -> list[float]:
        return [item[name] for item in items]

    states: list[str] = []
    for frame in frames:
        if not states or states[-1] != frame["state"]:
            states.append(frame["state"])

    return RunSummary(
        run_id=start["run_id"],
        platform=start["platform"],
        action_mode=start["detector_config"].get("action_mode"),
        status=end["status"] if end else "interrupted",
        frame_count=len(frames),
        fps=(len(frames) - 1) / elapsed if elapsed > 0 else None,
        inference=_stats(values(frames, "inference_latency_ms")),
        control=_stats(values(frames, "control_latency_ms")),
        end_to_end=_stats(values(frames, "end_to_end_latency_ms")),
        control_with_actions=_stats(values(with_actions, "control_latency_ms")),
        end_to_end_with_actions=_stats(values(with_actions, "end_to_end_latency_ms")),
        states=tuple(states),
        actions=tuple(
            (action["action"], action["success"], action["failure_reason"])
            for frame in frames
            for action in frame["actions"]
        ),
    )


def _stats_line(label: str, stats: LatencyStats | None) -> str:
    if stats is None:
        return f"{label}: 표본 없음"
    return f"{label}: 중앙값 {stats.median_ms:.1f} / p95 {stats.p95_ms:.1f} (n={stats.count})"


def format_summary(summary: RunSummary) -> str:
    fps = f"{summary.fps:.1f}" if summary.fps is not None else "계산 불가"
    lines = [
        f"run ID: {summary.run_id}",
        f"platform: {summary.platform}",
        f"action mode: {summary.action_mode or '기록 없음'}",
        f"run_end.status: {summary.status}",
        f"frame 수: {summary.frame_count}",
        f"FPS: {fps}",
        "",
        "latency (ms)",
        _stats_line("inference", summary.inference),
        _stats_line("control (전체 frame)", summary.control),
        _stats_line("control (action frame)", summary.control_with_actions),
        _stats_line("end-to-end (전체 frame)", summary.end_to_end),
        _stats_line("end-to-end (action frame)", summary.end_to_end_with_actions),
        "",
        f"상태 전이: {' -> '.join(summary.states) or '없음'}",
        "action:",
    ]
    for name, succeeded, reason in summary.actions:
        lines.append(f"  {name}: {'성공' if succeeded else f'실패 ({reason})'}")
    if not summary.actions:
        lines.append("  없음")
    if summary.action_mode == "real":
        lines.append("주의: --actions real의 미디어 성공은 물리 동작이 아닙니다.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log", type=Path, help="JSONL 실행 로그 경로")
    args = parser.parse_args(argv)
    try:
        with args.log.open(encoding="utf-8") as log:
            summary = summarize(json.loads(line) for line in log if line.strip())
    except (OSError, ValueError) as error:
        print(f"요약 실패: {error}")
        return 1
    print(format_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
