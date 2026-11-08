"""Manual smoke test for an attached OpenCV camera."""

from __future__ import annotations

import argparse
from typing import Any

from sleep_aware.config import settings

from .camera import CameraSourceError, OpenCVCameraSource

# A camera that is covered, asleep, or handing back a placeholder stream returns
# near-black frames; the pipeline would then log NO_FACE without any error.
BLACK_FRAME_MEAN = 1.0
PROBE_FRAMES = 15


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser using environment-backed defaults."""
    parser = argparse.ArgumentParser(description="Check frame capture from an attached camera.")
    parser.add_argument("--camera-index", type=int, default=settings.camera_index)
    parser.add_argument("--width", type=int, default=settings.camera_width)
    parser.add_argument("--height", type=int, default=settings.camera_height)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument(
        "--list",
        action="store_true",
        help="Probe camera indices and report image shape and mean brightness",
    )
    parser.add_argument("--list-max-index", type=int, default=3)
    return parser


def _mean_brightness(payload: Any) -> float | None:
    """Return the mean pixel value of a frame, or ``None`` for unknown payloads."""
    mean = getattr(payload, "mean", None)
    return float(mean()) if callable(mean) else None


def probe_cameras(
    max_index: int, width: int, height: int, frames: int = PROBE_FRAMES
) -> list[dict[str, Any]]:
    """Open each camera index once and describe what it returns.

    macOS hands index 0 to a Continuity Camera iPhone when one is nearby, so the
    operator needs a way to see which index is which before a demonstration.
    """
    reports: list[dict[str, Any]] = []
    for index in range(max_index + 1):
        try:
            with OpenCVCameraSource(
                camera_index=index, width=width, height=height
            ) as source:
                last = None
                # Read a few frames so auto-exposure settles before judging brightness.
                for _ in range(frames):
                    last = source.read()
        except CameraSourceError as error:
            reports.append({"index": index, "usable": False, "detail": str(error)})
            continue
        payload = last.payload if last is not None else None
        reports.append(
            {
                "index": index,
                "usable": True,
                "shape": getattr(payload, "shape", None),
                "mean_brightness": _mean_brightness(payload),
            }
        )
    return reports


def _print_reports(reports: list[dict[str, Any]]) -> None:
    for report in reports:
        if not report["usable"]:
            print(f"index {report['index']}: unavailable ({report['detail']})")
            continue
        brightness = report["mean_brightness"]
        note = ""
        if brightness is not None and brightness < BLACK_FRAME_MEAN:
            note = "  <- black frame; check lens cover or Continuity Camera (iPhone)"
        shown = "unknown" if brightness is None else f"{brightness:.1f}"
        print(f"index {report['index']}: shape={report['shape']}, mean_brightness={shown}{note}")


def main() -> int:
    """Capture a finite frame sample and report whether the camera is usable."""
    args = _parser().parse_args()
    if args.frames < 1:
        raise SystemExit("--frames must be at least 1")

    if args.list:
        reports = probe_cameras(args.list_max_index, args.width, args.height)
        _print_reports(reports)
        return 0 if any(report["usable"] for report in reports) else 1

    try:
        with OpenCVCameraSource(
            camera_index=args.camera_index,
            width=args.width,
            height=args.height,
        ) as source:
            first = source.read()
            last = first
            for _ in range(args.frames - 1):
                last = source.read()
    except CameraSourceError as error:
        print(f"Camera smoke test failed: {error}")
        return 1

    shape = getattr(last.payload, "shape", None)
    duration = last.timestamp - first.timestamp
    brightness = _mean_brightness(last.payload)
    print(
        "Camera smoke test passed: "
        f"index={source.camera_index}, frames={args.frames}, "
        f"shape={shape}, monotonic_duration={duration:.3f}s"
    )
    if brightness is not None and brightness < BLACK_FRAME_MEAN:
        print(
            "Warning: the last frame is black (mean brightness "
            f"{brightness:.1f}). Check the lens or another camera index. "
            "Use --list to compare available indices."
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
