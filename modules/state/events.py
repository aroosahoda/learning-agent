"""Append-only, schema-validated JSONL event log (Phase 1.5). Source of truth for resume."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from modules.schema_check import SchemaError, validate
from modules.state.atomic import file_lock
from modules.state.paths import AlvarPaths

_TAIL_WINDOW = 65536  # must exceed logging.max_event_bytes (capped at 65536 by config)
_RESERVED = {"t", "event", "session", "seq"}


class CorruptLogError(RuntimeError):
    """The log has damage beyond a torn final line. Never auto-repaired."""


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class EventLog:
    def __init__(self, paths: AlvarPaths, session_id: str, max_event_bytes: int = 16384) -> None:
        self.session_id = session_id
        self.path: Path = paths.events_file(session_id)
        self.max_event_bytes = max_event_bytes

    def append(self, event: str, /, **fields: Any) -> dict[str, Any]:
        clash = _RESERVED & fields.keys()
        if clash:
            raise ValueError(f"fields may not set reserved keys: {sorted(clash)}")
        with file_lock(self.path):
            seq = self._last_seq_repairing_tail() + 1
            record = {"t": utcnow(), "event": event, "session": self.session_id, "seq": seq, **fields}
            validate("event", record)
            line = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            if len(line) > self.max_event_bytes:
                raise ValueError(f"event is {len(line)} bytes; limit is {self.max_event_bytes}")
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, line)
                os.fsync(fd)
            finally:
                os.close(fd)
        return record

    def read(self) -> list[dict[str, Any]]:
        """Strictly read every event. Raises CorruptLogError on any inconsistency."""
        return read_events(self.path, self.session_id)

    # -- internals ------------------------------------------------------
    def _last_seq_repairing_tail(self) -> int:
        """Return last seq. A torn (unterminated) final line from a crash is quarantined."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return 0
        with open(self.path, "rb+") as f:
            size = f.seek(0, os.SEEK_END)
            base = max(0, size - _TAIL_WINDOW)
            f.seek(base)
            chunk = f.read()
            if not chunk.endswith(b"\n"):
                nl = chunk.rfind(b"\n")
                if nl == -1 and base > 0:
                    raise CorruptLogError(f"{self.path}: final line exceeds tail window")
                torn = chunk[nl + 1 :]
                with open(f"{self.path}.torn", "ab") as q:  # keep bytes for forensics
                    q.write(torn + b"\n")
                f.truncate(base + nl + 1)
                f.flush()
                os.fsync(f.fileno())
                chunk = chunk[: nl + 1]
            if not chunk:
                return 0
            lines = chunk.splitlines()
            if base > 0 and len(lines) == 1:
                raise CorruptLogError(f"{self.path}: final line exceeds tail window")
            try:
                return int(json.loads(lines[-1])["seq"])
            except (ValueError, KeyError, TypeError) as e:
                raise CorruptLogError(f"{self.path}: last line is not a valid event") from e


def read_events(path: Path, session_id: str | None = None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise CorruptLogError(f"{path}: unterminated final line (crash mid-write?)")
    for n, line in enumerate(raw.splitlines(), start=1):
        try:
            rec = json.loads(line)
            validate("event", rec)
        except (ValueError, SchemaError) as e:
            raise CorruptLogError(f"{path}:{n}: {e}") from e
        if rec["seq"] != n:
            raise CorruptLogError(f"{path}:{n}: expected seq {n}, found {rec['seq']}")
        if session_id and rec["session"] != session_id:
            raise CorruptLogError(f"{path}:{n}: belongs to session {rec['session']}")
        events.append(rec)
    return events
