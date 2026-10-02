"""Session init / resume by event replay (Phase 1.6)."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from modules.config import Config
from modules.state.atomic import atomic_write_text
from modules.state.events import CorruptLogError, EventLog, read_events
from modules.state.paths import AlvarPaths, slugify
from modules.state.states import State


class SessionError(RuntimeError):
    pass


@dataclass(frozen=True)
class SessionSnapshot:
    session_id: str
    topic: str
    state: State
    last_seq: int
    ended: bool


def replay(events: list[dict[str, Any]]) -> SessionSnapshot:
    """Fold events into current state. Pure function -> trivially testable."""
    if not events or events[0]["event"] != "session_started":
        raise CorruptLogError("log must begin with session_started")
    topic, state, ended = events[0]["topic"], State.GREET, False
    for e in events[1:]:
        if ended:
            raise CorruptLogError(f"event seq {e['seq']} after session_ended")
        if e["event"] == "state_transition":
            state = State(e["to"])
        elif e["event"] == "checkpoint":
            state = State(e["state"])
        elif e["event"] == "session_ended":
            ended = True
        elif e["event"] == "session_started":
            raise CorruptLogError(f"duplicate session_started at seq {e['seq']}")
    return SessionSnapshot(events[0]["session"], topic, state, events[-1]["seq"], ended)


class Session:
    def __init__(self, paths: AlvarPaths, snapshot: SessionSnapshot, config: Config) -> None:
        self.paths, self.snapshot, self.config = paths, snapshot, config
        self.log = EventLog(paths, snapshot.session_id, config.logging.max_event_bytes)

    @classmethod
    def start(cls, paths: AlvarPaths, topic: str, config: Config) -> Session:
        topic = topic.strip()
        if not topic or len(topic) > 200 or any(ord(c) < 32 for c in topic):
            raise SessionError("topic must be 1-200 printable characters")
        paths.init()
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        for _ in range(5):
            sid = f"{day}-{slugify(topic, 40)}-{secrets.token_hex(3)}"
            if not paths.events_file(sid).exists():
                break
        else:
            raise SessionError("could not allocate a unique session id")
        log = EventLog(paths, sid, config.logging.max_event_bytes)
        log.append("session_started", topic=topic)
        # json.dumps quotes the topic so user text cannot inject YAML/frontmatter keys
        stub = f"---\nsession: {sid}\ntopic: {json.dumps(topic)}\n---\n\n# Session: {slugify(topic)}\n"
        atomic_write_text(paths.session_file(sid), stub)
        return cls(paths, replay(log.read()), config)

    @classmethod
    def resume(cls, paths: AlvarPaths, session_id: str, config: Config) -> Session:
        events = read_events(paths.events_file(session_id), session_id)
        if not events:
            raise SessionError(f"no such session: {session_id}")
        snap = replay(events)
        if snap.ended:
            raise SessionError(f"session {session_id} already ended")
        log = EventLog(paths, session_id, config.logging.max_event_bytes)
        log.append("session_resumed", from_seq=snap.last_seq)
        return cls(paths, replay(log.read()), config)

    @classmethod
    def find_resumable(cls, paths: AlvarPaths) -> str | None:
        files = sorted(paths.events_dir().glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files:
            try:
                snap = replay(read_events(f, f.stem))
            except (CorruptLogError, ValueError):
                continue  # `validate` command reports these; don't resume damaged sessions
            if not snap.ended:
                return snap.session_id
        return None

    # -- mutations ------------------------------------------------------
    # EventLog.append only inspects the log tail (O(1)); Session therefore re-reads the WHOLE
    # log strictly BEFORE writing, so damage or a concurrent session_ended is caught before
    # another event is appended on top of it.
    def _refresh(self) -> None:
        self.snapshot = replay(self.log.read())

    def _append(self, event: str, /, **fields: Any) -> None:
        self._refresh()
        if self.snapshot.ended:
            raise SessionError(f"session {self.snapshot.session_id} already ended")
        self.log.append(event, **fields)
        self._refresh()

    def record_transition(self, to: State) -> None:
        # Phase 2.1 replaces this with a validated transition table.
        self._append("state_transition", **{"from": self.snapshot.state.value, "to": to.value})

    def checkpoint(self, summary: str) -> None:
        self._append("checkpoint", state=self.snapshot.state.value, summary=summary[:2000])

    def end(self, reason: str = "completed") -> None:
        self._append("session_ended", reason=reason)
