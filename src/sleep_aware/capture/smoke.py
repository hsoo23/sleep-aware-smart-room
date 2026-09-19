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
    parser = argparse.ArgumentParser(description="연결된 카메라의 프레임 입력을 확인합니다.")
    parser.add_argument("--camera-index", type=int, default=settings.camera_index)
    parser.add_argument("--width", type=int, default=settings.camera_width)
    parser.add_argument("--height", type=int, default=settings.camera_height)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument(
        "--list",
        action="store_true",
        help="사용 가능한 카메라 index를 순서대로 열어 해상도와 평균 밝기를 보고합니다",
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
            print(f"index {report['index']}: 사용 불가 ({report['detail']})")
            continue
        brightness = report["mean_brightness"]
        note = ""
        if brightness is not None and brightness < BLACK_FRAME_MEAN:
            note = "  ← 검은 화면입니다. 렌즈 가림 또는 연속성 카메라(iPhone)를 확인하세요"
        shown = "알 수 없음" if brightness is None else f"{brightness:.1f}"
        print(f"index {report['index']}: shape={report['shape']}, 평균 밝기={shown}{note}")


def main() -> int:
    """Capture a finite frame sample and report whether the camera is usable."""
    args = _parser().parse_args()
    if args.frames < 1:
        raise SystemExit("--frames는 1 이상이어야 합니다.")

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
        print(f"카메라 smoke test 실패: {error}")
        return 1

    shape = getattr(last.payload, "shape", None)
    duration = last.timestamp - first.timestamp
    brightness = _mean_brightness(last.payload)
    print(
        "카메라 smoke test 통과: "
        f"index={source.camera_index}, frames={args.frames}, "
        f"shape={shape}, monotonic_duration={duration:.3f}s"
    )
    if brightness is not None and brightness < BLACK_FRAME_MEAN:
        print(
            "경고: 마지막 프레임이 검은 화면입니다(평균 밝기 "
            f"{brightness:.1f}). 렌즈 가림 또는 다른 카메라 index를 확인하세요. "
            "--list 로 사용 가능한 index를 비교할 수 있습니다."
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
