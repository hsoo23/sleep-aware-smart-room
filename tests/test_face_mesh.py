from types import SimpleNamespace

import numpy as np
import pytest

from sleep_aware.pipeline import (
    LEFT_EYE_INDICES,
    RIGHT_EYE_INDICES,
    FaceMeshProcessingError,
    Frame,
    MediaPipeFaceMeshProcessor,
)


class FakeCv2:
    COLOR_BGR2RGB = 4

    @staticmethod
    def cvtColor(image, conversion):
        assert conversion == FakeCv2.COLOR_BGR2RGB
        return image[..., ::-1].copy()


class FakeFaceMesh:
    def __init__(self, result):
        self.result = result
        self.closed = False

    def process(self, image):
        assert image.flags.writeable is False
        return self.result

    def close(self):
        self.closed = True


def _processor(result):
    model = FakeFaceMesh(result)
    options = {}

    def factory(**kwargs):
        options.update(kwargs)
        return model

    processor = MediaPipeFaceMeshProcessor(
        cv2_module=FakeCv2,
        face_mesh_factory=factory,
    )
    return processor, model, options


def test_face_mesh_uses_legacy_indices_and_extracts_pixel_landmarks():
    points = [SimpleNamespace(x=index / 1000, y=index / 2000) for index in range(478)]
    face = SimpleNamespace(landmark=points)
    processor, _, options = _processor(SimpleNamespace(multi_face_landmarks=[face]))

    result = processor.process(Frame(4, 1.0, np.zeros((100, 200, 3), dtype=np.uint8)))

    assert result is not None
    assert tuple(point.x for point in result.left_eye) == pytest.approx(
        tuple(index / 5 for index in LEFT_EYE_INDICES)
    )
    assert tuple(point.y for point in result.right_eye) == pytest.approx(
        tuple(index / 20 for index in RIGHT_EYE_INDICES)
    )
    assert len(result.face_landmarks) == 478
    assert options == {
        "max_num_faces": 1,
        "refine_landmarks": True,
        "min_detection_confidence": 0.5,
        "min_tracking_confidence": 0.5,
    }


def test_face_mesh_distinguishes_no_face_from_processing_error():
    processor, _, _ = _processor(SimpleNamespace(multi_face_landmarks=[]))
    frame = Frame(8, 2.0, np.zeros((10, 10, 3), dtype=np.uint8))
    assert processor.process(frame) is None

    with pytest.raises(FaceMeshProcessingError, match="sequence 8"):
        processor.process(Frame(8, 2.0, object()))


def test_face_mesh_context_manager_closes_native_model():
    processor, model, _ = _processor(SimpleNamespace(multi_face_landmarks=[]))

    with processor:
        pass

    assert model.closed is True
    processor.close()
    with pytest.raises(FaceMeshProcessingError, match="closed"):
        processor.process(Frame(0, 0.0, np.zeros((1, 1, 3), dtype=np.uint8)))
