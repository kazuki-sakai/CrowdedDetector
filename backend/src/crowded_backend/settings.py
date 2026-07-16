from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    api_key: str
    data_dir: Path
    max_devices: int
    max_image_bytes: int
    queue_size: int
    detector: str
    yolo_model: str
    yolo_device: str
    yolo_confidence: float

    @classmethod
    def from_env(cls) -> "Settings":
        api_key = os.getenv("CROWDED_API_KEY", "").strip()
        if len(api_key) < 16:
            raise ValueError("CROWDED_API_KEY must contain at least 16 characters")
        detector = os.getenv("CROWDED_DETECTOR", "mock").strip().lower()
        if detector not in {"mock", "yolo"}:
            raise ValueError("CROWDED_DETECTOR must be 'mock' or 'yolo'")
        confidence = float(os.getenv("CROWDED_YOLO_CONFIDENCE", "0.35"))
        if not 0.0 < confidence <= 1.0:
            raise ValueError("CROWDED_YOLO_CONFIDENCE must be in (0, 1]")
        return cls(
            api_key=api_key,
            data_dir=Path(os.getenv("CROWDED_DATA_DIR", "data")),
            max_devices=_positive_int("CROWDED_MAX_DEVICES", 12),
            max_image_bytes=_positive_int("CROWDED_MAX_IMAGE_BYTES", 5 * 1024 * 1024),
            queue_size=_positive_int("CROWDED_QUEUE_SIZE", 24),
            detector=detector,
            yolo_model=os.getenv("CROWDED_YOLO_MODEL", "yolo11n.pt"),
            yolo_device=os.getenv("CROWDED_YOLO_DEVICE", "0"),
            yolo_confidence=confidence,
        )
