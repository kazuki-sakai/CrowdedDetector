from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path


def _boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean: {value}")


@dataclass(frozen=True)
class DeviceSettings:
    device_id: int
    location_id: int
    room_name: str
    zone_name: str
    backend_url: str
    api_token: str
    timeout_seconds: float
    verify_tls: bool
    camera_device: int
    interval_seconds: float
    width: int
    height: int
    jpeg_quality: int

    @classmethod
    def from_file(cls, path: Path) -> "DeviceSettings":
        parser = configparser.ConfigParser(interpolation=None)
        if not parser.read(path, encoding="utf-8"):
            raise FileNotFoundError(f"configuration file not found: {path}")
        device_id = parser.getint("device", "id")
        settings = cls(
            device_id=device_id,
            location_id=parser.getint("device", "location_id", fallback=device_id),
            room_name=parser.get("device", "room_name").strip(),
            zone_name=parser.get("device", "zone_name", fallback="").strip(),
            backend_url=parser.get("backend", "url").strip(),
            api_token=parser.get("backend", "token").strip(),
            timeout_seconds=parser.getfloat("backend", "timeout_seconds", fallback=20),
            verify_tls=_boolean(parser.get("backend", "verify_tls", fallback="true")),
            camera_device=parser.getint("camera", "device", fallback=0),
            interval_seconds=parser.getfloat("camera", "interval_seconds", fallback=10),
            width=parser.getint("camera", "width", fallback=1280),
            height=parser.getint("camera", "height", fallback=720),
            jpeg_quality=parser.getint("camera", "jpeg_quality", fallback=85),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not 1 <= self.device_id <= 24:
            raise ValueError("device.id must be between 1 and 24")
        if not 1 <= self.location_id <= 12:
            raise ValueError("device.location_id must be between 1 and 12")
        if (
            not self.room_name
            or len(self.room_name) > 100
            or "\n" in self.room_name
            or "\r" in self.room_name
        ):
            raise ValueError("device.room_name must contain 1 to 100 characters")
        if (
            len(self.zone_name) > 100
            or "\n" in self.zone_name
            or "\r" in self.zone_name
        ):
            raise ValueError("device.zone_name must contain at most 100 characters")
        if not self.backend_url.startswith(("http://", "https://")):
            raise ValueError("backend.url must be an HTTP(S) URL")
        if self.timeout_seconds <= 0 or self.interval_seconds <= 0:
            raise ValueError("timeouts and intervals must be positive")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("camera dimensions must be positive")
        if not 1 <= self.jpeg_quality <= 100:
            raise ValueError("camera.jpeg_quality must be between 1 and 100")
