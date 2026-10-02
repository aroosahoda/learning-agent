"""Crash-safe file writes and cross-platform locking."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from filelock import FileLock


def _fsync_dir(directory: Path) -> None:
    if os.name != "posix":  # Windows cannot fsync directories
        return
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_text(path: Path | str, text: str, mode: int = 0o600) -> None:
    """Write via temp file + fsync + rename so readers never see a half-written file."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    _fsync_dir(path.parent)


def atomic_write_json(path: Path | str, obj: Any) -> None:
    atomic_write_text(path, json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


@contextlib.contextmanager
def file_lock(target: Path | str, timeout: float = 10.0) -> Iterator[None]:
    """Advisory lock on '<target>.lock'. Works on Linux, macOS and Windows."""
    with FileLock(str(target) + ".lock", timeout=timeout):
        yield
