from __future__ import annotations

from contextlib import contextmanager
import fcntl
from pathlib import Path
from typing import Iterator


@contextmanager
def exclusive_file_lock(path: Path) -> Iterator[None]:
    """Block until an inter-process exclusive lock can be acquired."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Open read/write so the same descriptor is valid for both LOCK_EX and
    # LOCK_SH on Linux. A write-only descriptor makes LOCK_SH fail with EBADF.
    with path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def shared_file_lock(path: Path) -> Iterator[None]:
    """Block until an inter-process shared lock can be acquired."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
