from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from crowded_backend.settings import Settings


class SettingsTest(unittest.TestCase):
    def test_reads_random_detector_settings(self) -> None:
        environment = {
            "CROWDED_API_KEY": "test-key-1234567",
            "CROWDED_DETECTOR": "random",
            "CROWDED_RANDOM_MIN_COUNT": "4",
            "CROWDED_RANDOM_MAX_COUNT": "27",
            "CROWDED_RANDOM_SEED": "12345",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.detector, "random")
        self.assertEqual(settings.random_min_count, 4)
        self.assertEqual(settings.random_max_count, 27)
        self.assertEqual(settings.random_seed, 12345)

    def test_rejects_reversed_random_range(self) -> None:
        environment = {
            "CROWDED_API_KEY": "test-key-1234567",
            "CROWDED_DETECTOR": "random",
            "CROWDED_RANDOM_MIN_COUNT": "30",
            "CROWDED_RANDOM_MAX_COUNT": "10",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()


if __name__ == "__main__":
    unittest.main()
