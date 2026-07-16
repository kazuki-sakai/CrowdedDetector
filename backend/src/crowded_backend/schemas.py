from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Observation:
    device_id: int
    room_name: str
    image: bytes
    received_at: datetime

