"""Command-line entry point for reproducible mock runs and camera demonstrations."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

from sleep_aware.adapters import MockActionExecutor, RaspberryPiHttpActionExecutor
from sleep_aware.capture import OpenCVCameraSource
from sleep_aware.config import settings
from sleep_aware.control import ClosedLoopPolicy, Intention
from sleep_aware.detection import TemporalDrowsinessDetector
from sleep_aware.eventlog import JsonlEventLogger, RunMetadata, git_revision, new_run_id
from sleep_aware.eventlog.mock_run import run_mock
from sleep_aware.pipeline import BaselinePipeline, Frame, MediaPipeFaceMeshProcessor


class DisplayFrameSource:
    """Show camera frames and stop when the user presses ``q`` or Escape."""

    def __init__(self, source: OpenCVCameraSource, opencv: Any) -> None:
        self._source = source
        self._opencv = opencv

    def read(self) -> Frame | None:
        frame = self._source.read()
        self._opencv.imshow("sleep-aware-smart-room", frame.payload)
        key = self._opencv.waitKey(1) & 0xFF
        return None if key in {ord("q"), 27} else frame

    def close(self) -> None:
        self._opencv.destroyAllWindows()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--intention",
        choices=[item.value for item in Intention],
        default=Intention.WAKE.value,
        help="폐루프 동작 의도",
    )
    parser.add_argument(
        "--input",
        choices=("mock", "camera"),
        default="mock",
        help="결정적 mock 시나리오 또는 실제 카메라 입력",
    )
    parser.add_argument(
        "--actions",
        choices=("mock", "real"),
        default="mock",
        help="메모리 장치 또는 Raspberry Pi HTTP 동작",
    )
    parser.add_argument("--log-dir", type=Path, default=Path(settings.log_dir))
    parser.add_argument("--ear-threshold", type=float, default=settings.ear_threshold)
    parser.add_argument("--camera-index", type=int, default=settings.camera_index)
    parser.add_argument("--display", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--allow-insecure-http",
        action="store_true",
        help="격리된 개발망에서 Raspberry Pi 평문 HTTP를 명시적으로 허용",
    )
    return parser


def _add_note(error: BaseException, note: str) -> None:
    """Attach a note like ``BaseException.add_note`` (Python 3.11+) on Python 3.10 too."""
    notes = getattr(error, "__notes__", None)
    if notes is None:
        notes = []
        error.__notes__ = notes
    notes.append(note)


@contextmanager
def _closing_executor(executor: RaspberryPiHttpActionExecutor) -> Iterator[None]:
    """Close the executor without letting its failure hide an earlier cleanup error."""
    try:
        yield
    except BaseException as error:
        try:
            executor.close()
        except Exception as close_error:  # noqa: BLE001 - keep the primary error.
            _add_note(error, f"장치 실행기 종료도 실패했습니다: {close_error}")
        raise
    executor.close()


def _close_pipeline(pipeline: BaselinePipeline, policy: ClosedLoopPolicy) -> None:
    """Run policy cleanup and fail loudly if external device state may be left behind.

    Called from ``finally`` so the check also runs on Ctrl+C or pipeline errors; the
    original exception stays attached as ``__context__``.
    """
    pipeline.close()
    if policy.has_pending_cleanup:
        raise RuntimeError("종료 정리 동작이 완료되지 않았습니다. 장치 상태를 직접 확인하세요")


def run_camera(args: argparse.Namespace) -> Path:
    """Run the real camera pipeline and return the structured log path."""
    detector = TemporalDrowsinessDetector(
        ear_threshold=args.ear_threshold,
        drowsy_seconds=settings.drowsy_seconds,
        recovery_seconds=settings.recovery_seconds,
    )
    commit, dirty = git_revision(Path(__file__).resolve().parent)
    metadata = RunMetadata(
        run_id=new_run_id(),
        intention=Intention(args.intention),
        detector_name="B0-fixed-ear",
        detector_version="0.1.0",
        config_version="cli-camera-v1",
        detector_config={
            "ear_threshold": detector.ear_threshold,
            "drowsy_seconds": detector.drowsy_seconds,
            "recovery_seconds": detector.recovery_seconds,
            "source": "camera",
            "action_mode": args.actions,
        },
        git_commit=commit,
        git_dirty=dirty,
    )

    with ExitStack() as stack:
        # Open the log first so executor, camera, or MediaPipe start-up failures still get
        # run_end. ExitStack unwinds in reverse, so everything registered below (including
        # executor.close) finishes before the logger writes run_end.
        logger = stack.enter_context(JsonlEventLogger(args.log_dir, metadata))
        executor: Any
        if args.actions == "real":
            executor = RaspberryPiHttpActionExecutor(
                base_url=settings.pi_base_url,
                timeout_seconds=settings.pi_timeout_seconds,
                allow_insecure_http=args.allow_insecure_http,
            )
            stack.enter_context(_closing_executor(executor))
        else:
            executor = MockActionExecutor()
        source: Any = stack.enter_context(
            OpenCVCameraSource(
                camera_index=args.camera_index,
                width=settings.camera_width,
                height=settings.camera_height,
            )
        )
        processor = stack.enter_context(
            MediaPipeFaceMeshProcessor(
                max_num_faces=settings.face_mesh_max_num_faces,
                refine_landmarks=settings.face_mesh_refine_landmarks,
                min_detection_confidence=settings.face_mesh_min_detection_confidence,
                min_tracking_confidence=settings.face_mesh_min_tracking_confidence,
            )
        )
        if args.display:
            import cv2

            source = DisplayFrameSource(source, cv2)
            stack.callback(source.close)
        policy = ClosedLoopPolicy()
        pipeline = BaselinePipeline(
            frame_source=source,
            landmark_processor=processor,
            detector=detector,
            policy=policy,
            action_executor=executor,
            event_logger=logger,
            intention=Intention(args.intention),
        )
        try:
            for _ in pipeline.run():
                pass
        finally:
            _close_pipeline(pipeline, policy)
        return logger.path


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.input == "mock":
            if args.actions != "mock":
                raise ValueError("mock 입력은 안전한 mock 동작과 함께 사용해야 합니다")
            path = run_mock(
                args.log_dir,
                Intention(args.intention),
                failing_action=None,
            )
        else:
            path = run_camera(args)
    except KeyboardInterrupt:
        print("사용자 요청으로 안전하게 종료했습니다.")
        return 130
    except (OSError, RuntimeError, ValueError) as error:
        print(f"실행 실패: {error}")
        for note in getattr(error, "__notes__", ()):
            print(f"추가 실패: {note}")
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
