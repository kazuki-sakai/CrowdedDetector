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
        self.store = CsvStore(self.data_dir, max_devices=12)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_record_and_snapshot(self) -> None:
        now = datetime(2026, 7, 16, 1, 2, 3, tzinfo=timezone.utc)
        changed = self.store.record(1, "情報工学科", 7, now)
        self.assertFalse(changed)
        snapshot = self.store.snapshot()
        self.assertEqual(snapshot["rooms"][0]["id"], 1)
        self.assertEqual(snapshot["rooms"][0]["room_name"], "情報工学科")
        self.assertEqual(snapshot["rooms"][0]["person_count"], 7)

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
            self.store.record(13, "会場", 0, datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()

