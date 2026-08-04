from __future__ import annotations

import csv
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterable

from .locking import exclusive_file_lock, shared_file_lock


NAME_FIELDS = ("id", "location_id", "room_name", "zone_name", "updated_at")
COUNT_FIELDS = ("id", "person_count", "observed_at")
HISTORY_FIELDS = ("observed_at", "person_count")


class CsvStore:
    """Small, lock-protected CSV store suitable for up to a few dozen devices."""

    def __init__(
        self,
        data_dir: Path,
        max_devices: int = 24,
        max_locations: int = 12,
        device_stale_seconds: float = 35.0,
    ) -> None:
        if max_devices <= 0 or max_locations <= 0:
            raise ValueError("device and location limits must be positive")
        if device_stale_seconds <= 0:
            raise ValueError("device_stale_seconds must be positive")
        self.data_dir = data_dir
        self.max_devices = max_devices
        self.max_locations = max_locations
        self.device_stale_seconds = device_stale_seconds
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
        location_id: int | None = None,
        zone_name: str = "",
    ) -> bool:
        """Store one result and report whether the device assignment changed."""
        location_id = device_id if location_id is None else location_id
        zone_name = zone_name.strip()
        self._validate(device_id, location_id, room_name, zone_name, person_count)
        timestamp = self._isoformat(observed_at)
        with exclusive_file_lock(self.lock_path):
            names = self._read_by_id(self.names_path)
            previous = names.get(device_id)
            assignment_changed = previous is not None and (
                self._location_id(previous, device_id) != location_id
                or previous.get("room_name", "") != room_name
                or previous.get("zone_name", "") != zone_name
            )
            history_path = self.each_dir / f"crowded_{device_id:02d}.csv"

            if assignment_changed and history_path.exists():
                stamp = self._as_utc(observed_at).strftime("%Y%m%dT%H%M%S%fZ")
                backup = self.backup_dir / f"crowded_{device_id:02d}_{stamp}.csv"
                shutil.copy2(history_path, backup)
                history_rows: list[dict[str, str]] = []
            else:
                history_rows = self._read_rows(history_path)

            names[device_id] = {
                "id": str(device_id),
                "location_id": str(location_id),
                "room_name": room_name,
                "zone_name": zone_name,
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
            return assignment_changed

    def snapshot(self, now: datetime | None = None) -> dict[str, object]:
        current_time = self._as_utc(now or datetime.now(timezone.utc))
        with shared_file_lock(self.lock_path):
            names = self._read_by_id(self.names_path)
            counts = self._read_by_id(self.counts_path)

        locations: dict[int, list[tuple[int, dict[str, str]]]] = {}
        for device_id, metadata in names.items():
            location_id = self._location_id(metadata, device_id)
            if location_id is None:
                continue
            locations.setdefault(location_id, []).append((device_id, metadata))

        rooms: list[dict[str, object]] = []
        for location_id in sorted(locations):
            members = sorted(locations[location_id], key=lambda item: item[0])
            room_names = {
                metadata.get("room_name", "").strip()
                for _, metadata in members
                if metadata.get("room_name", "").strip()
            }
            room_name = members[0][1].get("room_name", "")
            device_rows: list[dict[str, object]] = []
            active_counts: list[int] = []
            observed_times: list[datetime] = []

            for device_id, metadata in members:
                count_row = counts.get(device_id)
                count_value = self._person_count(count_row)
                observed_time = self._observed_time(count_row)
                if observed_time is not None:
                    observed_times.append(observed_time)
                active = (
                    count_value is not None
                    and observed_time is not None
                    and (current_time - observed_time).total_seconds()
                    <= self.device_stale_seconds
                )
                if active:
                    active_counts.append(count_value)
                device_rows.append({
                    "id": device_id,
                    "zone_name": metadata.get("zone_name", ""),
                    "person_count": count_value if active else None,
                    "observed_at": (
                        self._isoformat(observed_time)
                        if observed_time is not None
                        else None
                    ),
                    "status": "ok" if active else "offline",
                })

            active_device_count = len(active_counts)
            if active_device_count == len(members):
                camera_status = "ok"
            elif active_device_count == 0:
                camera_status = "offline"
            else:
                camera_status = "partial"

            rooms.append({
                "id": location_id,
                "location_id": location_id,
                "room_name": room_name,
                "person_count": sum(active_counts) if active_counts else None,
                "observed_at": (
                    self._isoformat(max(observed_times)) if observed_times else None
                ),
                "camera_status": camera_status,
                "device_count": len(members),
                "active_device_count": active_device_count,
                "configuration_consistent": len(room_names) <= 1,
                "devices": device_rows,
            })
        return {
            "generated_at": self._isoformat(current_time),
            "rooms": rooms,
        }

    def _validate(
        self,
        device_id: int,
        location_id: int,
        room_name: str,
        zone_name: str,
        person_count: int,
    ) -> None:
        if not 1 <= device_id <= self.max_devices:
            raise ValueError(f"device_id must be between 1 and {self.max_devices}")
        if not 1 <= location_id <= self.max_locations:
            raise ValueError(
                f"location_id must be between 1 and {self.max_locations}"
            )
        if not room_name.strip() or len(room_name) > 100:
            raise ValueError("room_name must contain 1 to 100 characters")
        if len(zone_name) > 100 or "\n" in zone_name or "\r" in zone_name:
            raise ValueError("zone_name must contain at most 100 characters")
        if person_count < 0:
            raise ValueError("person_count must not be negative")

    def _location_id(
        self,
        metadata: dict[str, str],
        device_id: int,
    ) -> int | None:
        raw_value = metadata.get("location_id", "").strip() or str(device_id)
        try:
            location_id = int(raw_value)
        except ValueError:
            return None
        if not 1 <= location_id <= self.max_locations:
            return None
        return location_id

    @staticmethod
    def _person_count(count_row: dict[str, str] | None) -> int | None:
        if count_row is None:
            return None
        try:
            person_count = int(count_row["person_count"])
        except (KeyError, TypeError, ValueError):
            return None
        return person_count if person_count >= 0 else None

    @classmethod
    def _observed_time(
        cls,
        count_row: dict[str, str] | None,
    ) -> datetime | None:
        if count_row is None:
            return None
        raw_value = count_row.get("observed_at", "").strip()
        if not raw_value:
            return None
        try:
            return cls._as_utc(datetime.fromisoformat(raw_value.replace("Z", "+00:00")))
        except ValueError:
            return None

    @staticmethod
    def _isoformat(value: datetime) -> str:
        return CsvStore._as_utc(value).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

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
