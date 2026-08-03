from __future__ import annotations

from io import BytesIO
import logging
import random
from time import perf_counter
from typing import Protocol


LOGGER = logging.getLogger(__name__)


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


class RandomPersonDetector:
    """Test detector returning a configurable pseudo-random person count."""

    def __init__(
        self,
        min_count: int = 0,
        max_count: int = 30,
        seed: int | None = None,
    ) -> None:
        if min_count < 0:
            raise ValueError("min_count must not be negative")
        if max_count < min_count:
            raise ValueError("max_count must be greater than or equal to min_count")
        self._min_count = min_count
        self._max_count = max_count
        self._random = random.Random(seed)

    def count(self, image: bytes) -> int:
        if not image:
            raise ValueError("image is empty")
        return self._random.randint(self._min_count, self._max_count)


class YoloPersonDetector:
    """Ultralytics YOLO detector counting only COCO class 0 (person)."""

    def __init__(
        self,
        model_name: str,
        device: str,
        confidence: float,
        image_size: int = 640,
        warmup_width: int = 1280,
        warmup_height: int = 720,
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "YOLO dependencies are missing; install requirements-yolo.txt"
            ) from exc
        self._model = YOLO(model_name)
        self._device = device
        self._confidence = confidence
        self._image_size = image_size
        self._warm_up(model_name, warmup_width, warmup_height)

    def _warm_up(self, model_name: str, width: int, height: int) -> None:
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("Pillow is required for YOLO inference") from exc
        picture = Image.new("RGB", (width, height), color="black")
        started = perf_counter()
        try:
            self._predict(picture)
        finally:
            picture.close()
        LOGGER.info(
            "YOLO warm-up complete model=%s device=%s source_size=%dx%d "
            "image_size=%d elapsed_seconds=%.4f",
            model_name,
            self._device,
            width,
            height,
            self._image_size,
            perf_counter() - started,
        )

    def _predict(self, picture):
        return self._model.predict(
            source=picture,
            conf=self._confidence,
            classes=[0],
            device=self._device,
            imgsz=self._image_size,
            verbose=False,
        )

    def count(self, image: bytes) -> int:
        try:
            from PIL import Image, ImageOps
        except ImportError as exc:
            raise RuntimeError("Pillow is required for YOLO inference") from exc
        with Image.open(BytesIO(image)) as source:
            picture = ImageOps.exif_transpose(source).convert("RGB")
        try:
            results = self._predict(picture)
        finally:
            picture.close()
        if not results:
            return 0
        boxes = results[0].boxes
        return 0 if boxes is None else len(boxes)
