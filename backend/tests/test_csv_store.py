from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from crowded_backend.storage.csv_store import CsvStore


class CsvStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.store = CsvStore(
            self.data_dir,
            max_devices=24,
            max_locations=12,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_record_and_snapshot(self) -> None:
        now = datetime(2026, 7, 16, 1, 2, 3, tzinfo=timezone.utc)
        changed = self.store.record(1, "情報工学科", 7, now)
        self.assertFalse(changed)
        snapshot = self.store.snapshot(now=now)
        self.assertEqual(snapshot["rooms"][0]["id"], 1)
        self.assertEqual(snapshot["rooms"][0]["room_name"], "情報工学科")
        self.assertEqual(snapshot["rooms"][0]["person_count"], 7)
        self.assertEqual(snapshot["rooms"][0]["camera_status"], "ok")
        self.assertEqual(snapshot["rooms"][0]["device_count"], 1)
        self.assertEqual(snapshot["rooms"][0]["active_device_count"], 1)

    def test_room_change_archives_and_restarts_history(self) -> None:
        first = datetime(2026, 7, 16, 1, 0, tzinfo=timezone.utc)
        second = datetime(2026, 7, 16, 2, 0, tzinfo=timezone.utc)
        self.store.record(1, "旧会場", 3, first)
        changed = self.store.record(1, "新会場", 4, second)
        self.assertTrue(changed)
        backups = list((self.data_dir / "backup").glob("crowded_01_*.csv"))
        self.assertEqual(len(backups), 1)
        with (self.data_dir / "each" / "crowded_01.csv").open(
            encoding="utf-8", newline=""
        ) as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(rows, [{"observed_at": "2026-07-16T02:00:00Z", "person_count": "4"}])

    def test_rejects_out_of_range_id(self) -> None:
        with self.assertRaises(ValueError):
            self.store.record(25, "会場", 0, datetime.now(timezone.utc))

    def test_aggregates_devices_assigned_to_the_same_location(self) -> None:
        now = datetime(2026, 7, 16, 3, 0, tzinfo=timezone.utc)
        self.store.record(
            13,
            "大体育館",
            4,
            now,
            location_id=3,
            zone_name="左側",
        )
        self.store.record(
            14,
            "大体育館",
            6,
            now,
            location_id=3,
            zone_name="右側",
        )

        room = self.store.snapshot(now=now)["rooms"][0]
        self.assertEqual(room["id"], 3)
        self.assertEqual(room["person_count"], 10)
        self.assertEqual(room["camera_status"], "ok")
        self.assertEqual(room["device_count"], 2)
        self.assertEqual(room["active_device_count"], 2)
        self.assertEqual(
            [device["zone_name"] for device in room["devices"]],
            ["左側", "右側"],
        )

    def test_excludes_stale_device_and_reports_partial_or_offline(self) -> None:
        now = datetime(2026, 7, 16, 4, 0, tzinfo=timezone.utc)
        self.store.record(
            13,
            "大体育館",
            4,
            now,
            location_id=3,
            zone_name="左側",
        )
        self.store.record(
            14,
            "大体育館",
            6,
            now,
            location_id=3,
            zone_name="右側",
        )

        partial = self.store.snapshot(
            now=datetime(2026, 7, 16, 4, 0, 36, tzinfo=timezone.utc)
        )["rooms"][0]
        self.assertIsNone(partial["person_count"])
        self.assertEqual(partial["camera_status"], "offline")

        self.store.record(
            13,
            "大体育館",
            5,
            datetime(2026, 7, 16, 4, 0, 40, tzinfo=timezone.utc),
            location_id=3,
            zone_name="左側",
        )
        partial = self.store.snapshot(
            now=datetime(2026, 7, 16, 4, 0, 40, tzinfo=timezone.utc)
        )["rooms"][0]
        self.assertEqual(partial["person_count"], 5)
        self.assertEqual(partial["camera_status"], "partial")
        self.assertEqual(partial["active_device_count"], 1)

    def test_reports_inconsistent_room_names_for_one_location(self) -> None:
        now = datetime(2026, 7, 16, 4, 30, tzinfo=timezone.utc)
        self.store.record(13, "大体育館", 4, now, location_id=3)
        self.store.record(14, "体育館", 6, now, location_id=3)

        room = self.store.snapshot(now=now)["rooms"][0]
        self.assertEqual(room["room_name"], "大体育館")
        self.assertFalse(room["configuration_consistent"])

    def test_reads_legacy_name_csv_as_one_location_per_device(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            data_dir.joinpath("ID_name.csv").write_text(
                "id,room_name,updated_at\n"
                "2,旧形式会場,2026-07-16T05:00:00Z\n",
                encoding="utf-8",
            )
            data_dir.joinpath("crowded.csv").write_text(
                "id,person_count,observed_at\n"
                "2,9,2026-07-16T05:00:00Z\n",
                encoding="utf-8",
            )
            store = CsvStore(data_dir, max_devices=12, max_locations=12)
            room = store.snapshot(
                now=datetime(2026, 7, 16, 5, 0, tzinfo=timezone.utc)
            )["rooms"][0]

        self.assertEqual(room["id"], 2)
        self.assertEqual(room["room_name"], "旧形式会場")
        self.assertEqual(room["person_count"], 9)


if __name__ == "__main__":
    unittest.main()
