import json
import multiprocessing as mp
from pathlib import Path

import pytest

from modules.state.events import CorruptLogError, EventLog, read_events

SID = "2026-09-28-topic-abcdef"


def test_append_assigns_increasing_seq_and_validates(paths):
    log = EventLog(paths, SID)
    assert log.append("session_started", topic="t")["seq"] == 1
    assert log.append("state_transition", **{"from": "GREET", "to": "PLAN"})["seq"] == 2
    assert [e["seq"] for e in log.read()] == [1, 2]


def test_invalid_events_are_rejected_and_not_written(paths):
    log = EventLog(paths, SID)
    with pytest.raises(Exception):
        log.append("not_an_event")
    with pytest.raises(Exception):
        log.append("state_transition", to="PLAN")  # missing 'from'
    with pytest.raises(Exception):
        log.append("quiz_answered", node="x", correct=True, confidence="high")  # bad node id
    assert not log.path.exists() or log.path.read_bytes() == b""


def test_reserved_keys_cannot_be_overridden(paths):
    with pytest.raises(ValueError):
        EventLog(paths, SID).append("session_started", topic="t", seq=99)


def test_newlines_in_values_cannot_forge_extra_records(paths):
    log = EventLog(paths, SID)
    log.append("session_started", topic='x"}\n{"event":"session_ended"')
    assert len(log.read()) == 1 and len(log.path.read_text().splitlines()) == 1


def test_oversized_event_rejected(paths):
    log = EventLog(paths, SID, max_event_bytes=1024)
    with pytest.raises(ValueError):
        log.append("checkpoint", state="GREET", summary="x" * 1500)


def test_torn_tail_is_quarantined_then_log_continues(paths):
    log = EventLog(paths, SID)
    log.append("session_started", topic="t")
    with open(log.path, "ab") as f:
        f.write(b'{"t":"2026-09-28T00:00:00Z","event":"chec')  # crash mid-write
    with pytest.raises(CorruptLogError):
        log.read()  # strict reader refuses
    rec = log.append("checkpoint", state="GREET")  # writer repairs the tail
    assert rec["seq"] == 2
    assert len(log.read()) == 2
    assert b"chec" in Path(f"{log.path}.torn").read_bytes()


def test_mid_file_corruption_is_never_silently_skipped(paths):
    log = EventLog(paths, SID)
    log.append("session_started", topic="t")
    log.append("checkpoint", state="GREET")
    lines = log.path.read_text().splitlines()
    log.path.write_text("garbage\n" + lines[1] + "\n")
    with pytest.raises(CorruptLogError):
        log.read()


def test_seq_gap_and_foreign_session_detected(paths):
    log = EventLog(paths, SID)
    log.append("session_started", topic="t")
    log.append("checkpoint", state="GREET")
    lines = log.path.read_text().splitlines()
    log.path.write_text(lines[0] + "\n" + lines[1].replace('"seq":2', '"seq":5') + "\n")
    with pytest.raises(CorruptLogError):
        read_events(log.path, SID)
    log.path.write_text(lines[0].replace(SID, "2026-09-28-other-000000") + "\n")
    with pytest.raises(CorruptLogError):
        read_events(log.path, SID)


def _worker(args):
    root, n = args
    from modules.state.paths import AlvarPaths

    log = EventLog(AlvarPaths(root), SID)
    for _ in range(n):
        log.append("checkpoint", state="GREET")


def test_concurrent_writers_never_duplicate_or_lose_seq(paths):
    EventLog(paths, SID).append("session_started", topic="t")
    with mp.get_context("spawn").Pool(4) as pool:
        pool.map(_worker, [(paths.root, 15)] * 4)
    events = EventLog(paths, SID).read()
    assert [e["seq"] for e in events] == list(range(1, 62))
    json.dumps(events)
