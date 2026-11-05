"""Command-line entry point for reproducible mock runs and camera demonstrations."""

from __future__ import annotations

import argparse
import os
import signal
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

from sleep_aware.adapters import (
    CompositeActionExecutor,
    MacOSChromeMediaActionExecutor,
    MockActionExecutor,
    RaspberryPiHttpActionExecutor,
    SessionActionExecutor,
)
from sleep_aware.capture import OpenCVCameraSource
from sleep_aware.config import settings
from sleep_aware.control import Action, ClosedLoopPolicy, Intention
from sleep_aware.detection import TemporalDrowsinessDetector
from sleep_aware.eventlog import JsonlEventLogger, RunMetadata, git_revision, new_run_id
from sleep_aware.eventlog.mock_run import run_mock
from sleep_aware.pipeline import BaselinePipeline, Frame, create_landmark_processor

NO_DISPLAY_HINT = "화면이 없는 환경에서는 --no-display를 사용하세요"


class BoundedFrameSource:
    """Stop a live source after ``max_frames`` so a run ends without Ctrl+C."""

    def __init__(self, source: Any, max_frames: int) -> None:
        if max_frames < 1:
            raise ValueError("max_frames must be positive")
        self._source = source
        self._remaining = max_frames

    def read(self) -> Frame | None:
        if self._remaining <= 0:
            return None
        self._remaining -= 1
        return self._source.read()


class DisplayFrameSource:
    """Show camera frames and stop when the user presses ``q`` or Escape."""

    def __init__(self, source: OpenCVCameraSource, opencv: Any) -> None:
        self._source = source
        self._opencv = opencv

    def read(self) -> Frame | None:
        frame = self._source.read()
        try:
            self._opencv.imshow("sleep-aware-smart-room", frame.payload)
            key = self._opencv.waitKey(1) & 0xFF
        except self._opencv.error as error:
            raise RuntimeError(f"화면을 표시하지 못했습니다. {NO_DISPLAY_HINT}") from error
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
        choices=("mock", "real", "host"),
        default="mock",
        help=(
            "mock: 모든 동작을 메모리 장치로 실행, "
            "real: 모든 동작을 Raspberry Pi HTTP로 전송, "
            "host: 미디어는 이 호스트(macOS Chrome), 조명·부저는 Raspberry Pi HTTP, "
            "세션은 로컬 세션 추적기가 담당"
        ),
    )
    parser.add_argument("--log-dir", type=Path, default=Path(settings.log_dir))
    parser.add_argument("--ear-threshold", type=float, default=settings.ear_threshold)
    parser.add_argument("--camera-index", type=int, default=settings.camera_index)
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="카메라 입력에서 처리할 최대 frame 수 (0이면 제한 없음)",
    )
    parser.add_argument(
        "--face-landmarker-model",
        default=settings.face_landmarker_model,
        help="MediaPipe Tasks Face Landmarker 모델 경로 (legacy solutions 환경에서는 무시)",
    )
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


def _build_executor(args: argparse.Namespace) -> Any:
    """Create the action executor for the requested device combination."""
    if args.actions == "mock":
        return MockActionExecutor()

    http_executor = RaspberryPiHttpActionExecutor(
        base_url=settings.pi_base_url,
        timeout_seconds=settings.pi_timeout_seconds,
        allow_insecure_http=args.allow_insecure_http,
    )
    if args.actions == "real":
        return http_executor

    # host: media stays on this machine; the lamp and buzzer remain on the Raspberry Pi.
    media = MacOSChromeMediaActionExecutor()
    session = SessionActionExecutor()
    return CompositeActionExecutor(
        {
            Action.PAUSE_MEDIA: media,
            Action.PLAY_MEDIA: media,
            Action.LIGHT_OFF: http_executor,
            Action.LIGHT_ON: http_executor,
            Action.BUZZER_ALERT: http_executor,
            Action.START_SESSION: session,
            Action.END_SESSION: session,
        }
    )


def _require_display() -> None:
    """Fail clearly on a headless Linux host, where OpenCV's GUI backend may abort the process.

    An abort skips every cleanup below, so this has to be decided before ``imshow``.
    """
    if sys.platform == "linux" and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        raise RuntimeError(f"DISPLAY가 설정되어 있지 않습니다. {NO_DISPLAY_HINT}")


def _interrupt(*_: object) -> None:
    raise KeyboardInterrupt


@contextmanager
def _cleanup_on_termination() -> Iterator[None]:
    """Route SIGTERM and SIGHUP (kill, a dropped SSH session) through the cleanup path."""
    names = ("SIGTERM", "SIGHUP")
    numbers = [getattr(signal, name) for name in names if hasattr(signal, name)]
    previous = {number: signal.signal(number, _interrupt) for number in numbers}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


@contextmanager
def _closing_executor(executor: Any) -> Iterator[None]:
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
        executor: Any = _build_executor(args)
        if hasattr(executor, "close"):
            stack.enter_context(_closing_executor(executor))
        source: Any = stack.enter_context(
            OpenCVCameraSource(
                camera_index=args.camera_index,
                width=settings.camera_width,
                height=settings.camera_height,
            )
        )
        processor = stack.enter_context(
            create_landmark_processor(
                model_path=args.face_landmarker_model,
                max_num_faces=settings.face_mesh_max_num_faces,
                refine_landmarks=settings.face_mesh_refine_landmarks,
                min_detection_confidence=settings.face_mesh_min_detection_confidence,
                min_tracking_confidence=settings.face_mesh_min_tracking_confidence,
            )
        )
        if args.display:
            _require_display()
            import cv2

            source = DisplayFrameSource(source, cv2)
            stack.callback(source.close)
        if args.max_frames:
            source = BoundedFrameSource(source, args.max_frames)
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
            with _cleanup_on_termination():
                path = run_camera(args)
    except KeyboardInterrupt:
        print("중단 요청으로 안전하게 종료했습니다.")
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
