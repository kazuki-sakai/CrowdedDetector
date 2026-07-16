from __future__ import annotations

import csv
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterable

from .locking import exclusive_file_lock, shared_file_lock


NAME_FIELDS = ("id", "room_name", "updated_at")
COUNT_FIELDS = ("id", "person_count", "observed_at")
HISTORY_FIELDS = ("observed_at", "person_count")


class CsvStore:
    """Small, lock-protected CSV store suitable for up to a few dozen devices."""

    def __init__(self, data_dir: Path, max_devices: int = 12) -> None:
        self.data_dir = data_dir
        self.max_devices = max_devices
        self.names_path = data_dir / "ID_name.csv"
        self.counts_path = data_dir / "crowded.csv"
        self.each_dir = data_dir / "each"
        self.backup_dir = data_dir / "backup"
        self.lock_path = data_dir / ".store.lock"
        self.each_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path):
            if not self.names_path.exists():
                self._atomic_write(self.names_path, NAME_FIELDS, [])
            if not self.counts_path.exists():
                self._atomic_write(self.counts_path, COUNT_FIELDS, [])

    def record(
        self,
        device_id: int,
        room_name: str,
        person_count: int,
        observed_at: datetime,
    ) -> bool:
        """Store one result and return True when the room name changed."""
        self._validate(device_id, room_name, person_count)
        timestamp = self._isoformat(observed_at)
        with exclusive_file_lock(self.lock_path):
            names = self._read_by_id(self.names_path)
            previous = names.get(device_id)
            name_changed = previous is not None and previous["room_name"] != room_name
            history_path = self.each_dir / f"crowded_{device_id:02d}.csv"

            if name_changed and history_path.exists():
                stamp = observed_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                backup = self.backup_dir / f"crowded_{device_id:02d}_{stamp}.csv"
                shutil.copy2(history_path, backup)
                history_rows: list[dict[str, str]] = []
            else:
                history_rows = self._read_rows(history_path)

            names[device_id] = {
                "id": str(device_id),
                "room_name": room_name,
                "updated_at": timestamp,
            }
            self._atomic_write(self.names_path, NAME_FIELDS, self._sorted_rows(names))

            history_rows.append({
                "observed_at": timestamp,
                "person_count": str(person_count),
            })
            self._atomic_write(history_path, HISTORY_FIELDS, history_rows)

            counts = self._read_by_id(self.counts_path)
            counts[device_id] = {
                "id": str(device_id),
                "person_count": str(person_count),
                "observed_at": timestamp,
            }
            self._atomic_write(self.counts_path, COUNT_FIELDS, self._sorted_rows(counts))
            return name_changed

    def snapshot(self) -> dict[str, object]:
        with shared_file_lock(self.lock_path):
            names = self._read_by_id(self.names_path)
            counts = self._read_by_id(self.counts_path)
        rooms: list[dict[str, object]] = []
        for device_id in sorted(names):
            count = counts.get(device_id)
            rooms.append({
                "id": device_id,
                "room_name": names[device_id]["room_name"],
                "person_count": int(count["person_count"]) if count else None,
                "observed_at": count["observed_at"] if count else None,
            })
        return {
            "generated_at": self._isoformat(datetime.now(timezone.utc)),
            "rooms": rooms,
        }

    def _validate(self, device_id: int, room_name: str, person_count: int) -> None:
        if not 1 <= device_id <= self.max_devices:
            raise ValueError(f"device_id must be between 1 and {self.max_devices}")
        if not room_name.strip() or len(room_name) > 100:
            raise ValueError("room_name must contain 1 to 100 characters")
        if person_count < 0:
            raise ValueError("person_count must not be negative")

    @staticmethod
    def _isoformat(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _read_rows(path: Path) -> list[dict[str, str]]:
        if not path.exists() or path.stat().st_size == 0:
            return []
        with path.open("r", encoding="utf-8", newline="") as source:
            return list(csv.DictReader(source))

    def _read_by_id(self, path: Path) -> dict[int, dict[str, str]]:
        rows: dict[int, dict[str, str]] = {}
        for row in self._read_rows(path):
            try:
                device_id = int(row["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if 1 <= device_id <= self.max_devices:
                rows[device_id] = row
        return rows

    @staticmethod
    def _sorted_rows(rows: dict[int, dict[str, str]]) -> Iterable[dict[str, str]]:
        return (rows[key] for key in sorted(rows))

    @staticmethod
    def _atomic_write(
        path: Path,
        fields: tuple[str, ...],
        rows: Iterable[dict[str, str]],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp_name, path)
        except BaseException:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

