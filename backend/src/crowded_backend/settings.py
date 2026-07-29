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
    random_min_count: int
    random_max_count: int
    random_seed: int | None
    yolo_model: str
    yolo_device: str
    yolo_confidence: float

    @classmethod
    def from_env(cls) -> "Settings":
        api_key = os.getenv("CROWDED_API_KEY", "").strip()
        if len(api_key) < 16:
            raise ValueError("CROWDED_API_KEY must contain at least 16 characters")
        detector = os.getenv("CROWDED_DETECTOR", "mock").strip().lower()
        if detector not in {"mock", "random", "yolo"}:
            raise ValueError("CROWDED_DETECTOR must be 'mock', 'random', or 'yolo'")
        random_min_count = int(os.getenv("CROWDED_RANDOM_MIN_COUNT", "0"))
        random_max_count = int(os.getenv("CROWDED_RANDOM_MAX_COUNT", "30"))
        if random_min_count < 0:
            raise ValueError("CROWDED_RANDOM_MIN_COUNT must not be negative")
        if random_max_count < random_min_count:
            raise ValueError(
                "CROWDED_RANDOM_MAX_COUNT must be greater than or equal to "
                "CROWDED_RANDOM_MIN_COUNT"
            )
        random_seed_value = os.getenv("CROWDED_RANDOM_SEED", "").strip()
        random_seed = int(random_seed_value) if random_seed_value else None
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
            random_min_count=random_min_count,
            random_max_count=random_max_count,
            random_seed=random_seed,
            yolo_model=os.getenv("CROWDED_YOLO_MODEL", "yolo11n.pt"),
            yolo_device=os.getenv("CROWDED_YOLO_DEVICE", "0"),
            yolo_confidence=confidence,
        )
