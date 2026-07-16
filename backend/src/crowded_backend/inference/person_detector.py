from __future__ import annotations

from io import BytesIO
from typing import Protocol


class PersonDetector(Protocol):
    def count(self, image: bytes) -> int: ...


class MockPersonDetector:
    """Deterministic detector for wiring and API tests."""

    def __init__(self, count: int = 0) -> None:
        self.result = count

    def count(self, image: bytes) -> int:
        if not image:
            raise ValueError("image is empty")
        return self.result


class YoloPersonDetector:
    """Ultralytics YOLO detector counting only COCO class 0 (person)."""

    def __init__(self, model_name: str, device: str, confidence: float) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "YOLO dependencies are missing; install requirements-yolo.txt"
            ) from exc
        self._model = YOLO(model_name)
        self._device = device
        self._confidence = confidence

    def count(self, image: bytes) -> int:
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("Pillow is required for YOLO inference") from exc
        picture = Image.open(BytesIO(image)).convert("RGB")
        results = self._model.predict(
            source=picture,
            conf=self._confidence,
            classes=[0],
            device=self._device,
            verbose=False,
        )
        if not results:
            return 0
        boxes = results[0].boxes
        return 0 if boxes is None else len(boxes)

