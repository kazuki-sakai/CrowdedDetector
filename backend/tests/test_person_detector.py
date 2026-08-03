from __future__ import annotations

import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from crowded_backend.inference.person_detector import (
    RandomPersonDetector,
    YoloPersonDetector,
)


class RandomPersonDetectorTest(unittest.TestCase):
    def test_results_stay_inside_configured_range(self) -> None:
        detector = RandomPersonDetector(min_count=10, max_count=20, seed=12345)
        results = [detector.count(b"image") for _ in range(100)]
        self.assertTrue(all(10 <= result <= 20 for result in results))
        self.assertGreater(len(set(results)), 1)

    def test_seed_reproduces_sequence(self) -> None:
        first = RandomPersonDetector(seed=9876)
        second = RandomPersonDetector(seed=9876)
        self.assertEqual(
            [first.count(b"image") for _ in range(10)],
            [second.count(b"image") for _ in range(10)],
        )

    def test_rejects_invalid_range(self) -> None:
        with self.assertRaises(ValueError):
            RandomPersonDetector(min_count=-1, max_count=10)
        with self.assertRaises(ValueError):
            RandomPersonDetector(min_count=20, max_count=10)


class _FakePicture:
    def __init__(self, size: tuple[int, int]) -> None:
        self.size = size
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def convert(self, _mode: str):
        return _FakePicture(self.size)

    def close(self) -> None:
        self.closed = True


class _FakeImage:
    @staticmethod
    def new(_mode: str, size: tuple[int, int], color: str):
        del color
        return _FakePicture(size)

    @staticmethod
    def open(_source):
        return _FakePicture((1280, 720))


class _FakeImageOps:
    @staticmethod
    def exif_transpose(picture):
        return picture


class _FakeBoxes:
    def __len__(self) -> int:
        return 3


class _FakeResult:
    boxes = _FakeBoxes()


class _FakeYolo:
    instance = None

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.calls = []
        _FakeYolo.instance = self

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        return [_FakeResult()]


class YoloPersonDetectorTest(unittest.TestCase):
    def test_warms_up_and_counts_only_people(self) -> None:
        ultralytics = ModuleType("ultralytics")
        ultralytics.YOLO = _FakeYolo
        pillow = ModuleType("PIL")
        pillow.Image = _FakeImage
        pillow.ImageOps = _FakeImageOps

        with patch.dict(
            sys.modules,
            {"ultralytics": ultralytics, "PIL": pillow},
        ):
            detector = YoloPersonDetector(
                model_name="test-model.pt",
                device="0",
                confidence=0.35,
                image_size=640,
                warmup_width=1280,
                warmup_height=720,
            )
            count = detector.count(b"image")

        self.assertEqual(count, 3)
        self.assertIsNotNone(_FakeYolo.instance)
        calls = _FakeYolo.instance.calls
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["source"].size, (1280, 720))
        self.assertEqual(calls[1]["classes"], [0])
        self.assertEqual(calls[1]["device"], "0")
        self.assertEqual(calls[1]["imgsz"], 640)


if __name__ == "__main__":
    unittest.main()
