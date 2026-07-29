from __future__ import annotations

import fcntl
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from crowded_backend.storage.locking import exclusive_file_lock, shared_file_lock


class FileLockTest(unittest.TestCase):
    def test_lock_file_is_opened_read_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".store.lock"
            access_modes: list[int] = []

            def inspect_descriptor(descriptor: int, operation: int) -> None:
                del operation
                flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
                access_modes.append(flags & os.O_ACCMODE)

            with patch(
                "crowded_backend.storage.locking.fcntl.flock",
                side_effect=inspect_descriptor,
            ):
                with exclusive_file_lock(path):
                    pass
                with shared_file_lock(path):
                    pass

            self.assertEqual(access_modes, [os.O_RDWR] * 4)


if __name__ == "__main__":
    unittest.main()
