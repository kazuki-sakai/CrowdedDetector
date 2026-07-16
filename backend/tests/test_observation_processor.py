from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from crowded_backend.inference.person_detector import MockPersonDetector
from crowded_backend.schemas import Observation
from crowded_backend.services.observation_processor import ObservationProcessor
from crowded_backend.storage.csv_store import CsvStore


class ObservationProcessorTest(unittest.TestCase):
    def test_detector_result_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = CsvStore(Path(directory))
            processor = ObservationProcessor(MockPersonDetector(6), store)
            count = processor.process(
                Observation(
                    device_id=2,
                    room_name="部活動展示",
                    image=b"test-image",
                    received_at=datetime(2026, 7, 16, tzinfo=timezone.utc),
                )
            )
            room = store.snapshot()["rooms"][0]
        self.assertEqual(count, 6)
        self.assertEqual(room["person_count"], 6)


if __name__ == "__main__":
    unittest.main()

