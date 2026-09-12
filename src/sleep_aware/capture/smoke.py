"""Manual smoke test for an attached OpenCV camera."""

from __future__ import annotations

import argparse

from sleep_aware.config import settings

from .camera import CameraSourceError, OpenCVCameraSource


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="연결된 카메라의 프레임 입력을 확인합니다.")
    parser.add_argument("--camera-index", type=int, default=settings.camera_index)
    parser.add_argument("--width", type=int, default=settings.camera_width)
    parser.add_argument("--height", type=int, default=settings.camera_height)
    parser.add_argument("--frames", type=int, default=30)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.frames < 1:
        raise SystemExit("--frames는 1 이상이어야 합니다.")

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
    print(
        "카메라 smoke test 통과: "
        f"index={source.camera_index}, frames={args.frames}, "
        f"shape={shape}, monotonic_duration={duration:.3f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
