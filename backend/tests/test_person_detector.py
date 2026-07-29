from __future__ import annotations

import unittest

from crowded_backend.inference.person_detector import RandomPersonDetector


class RandomPersonDetectorTest(unittest.TestCase):
    def test_results_stay_inside_configured_range(self) -> None:
        detector = RandomPersonDetector(min_count=10, max_count=20, seed=12345)
        results = [detector.count(b"image") for _ in range(100)]
        self.assertTrue(all(10 <= result <= 20 for result in results))
        self.assertGreater(len(set(results)), 1)

    def test_seed_reproduces_sequence(self) -> None:
        first = RandomPersonDetector(seed=9876)
        second = RandomPersonDetector(seed=9876)
        self.assertEqual(
            [first.count(b"image") for _ in range(10)],
            [second.count(b"image") for _ in range(10)],
        )

    def test_rejects_invalid_range(self) -> None:
        with self.assertRaises(ValueError):
            RandomPersonDetector(min_count=-1, max_count=10)
        with self.assertRaises(ValueError):
            RandomPersonDetector(min_count=20, max_count=10)


if __name__ == "__main__":
    unittest.main()
