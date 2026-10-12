import multiprocessing as mp
import os
import time
from pathlib import Path
from typing import Any

import pytest

from modules.state.paths import AlvarPaths, SessionLockError, UnsafePathError, slugify

SID = "2026-01-01-differential-geometry-123456"
OTHER_SID = "2026-01-01-complex-analysis-654321"


# Top-level functions for multiprocessing (spawn-safe on Windows & POSIX)
def _lock_holder_worker(root: Path, session_id: str, ready_event: Any, stop_event: Any) -> None:
    paths = AlvarPaths(root)
    with paths.session_lock(session_id):
        ready_event.set()
        stop_event.wait(timeout=10)


def _contending_worker(root: Path, session_id: str, queue: mp.Queue) -> None:  # type: ignore[type-arg]
    paths = AlvarPaths(root)
    try:
        with paths.session_lock(session_id, timeout=0.0):
            queue.put("acquired")
    except SessionLockError:
        queue.put("locked")


def _serial_writer_worker(root: Path, session_id: str, text: str) -> None:
    paths = AlvarPaths(root)
    with paths.session_lock(session_id, timeout=10.0):
        target = paths.session_file(session_id)
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        time.sleep(0.05)  # simulate driving session work under lock
        target.write_text(current + text, encoding="utf-8")


def test_init_creates_layout_idempotently_and_private(tmp_path):
    p = AlvarPaths.for_project(tmp_path)
    p.init()
    p.learner_md.write_text("keep me")
    p.review_queue.write_text('{"version": 1, "cards": []}')
    p.init()
    assert p.learner_md.read_text() == "keep me"
    assert p.review_queue.read_text() == '{"version": 1, "cards": []}'
    for sub in ("maps", "sessions", "events", "visuals", "cache/sources", "cache"):
        assert (p.root / sub).is_dir()
    if os.name == "posix":
        assert oct((p.root / "cache").stat().st_mode & 0o777) == "0o700"
        assert oct(p.root.stat().st_mode & 0o777) == "0o700"
        assert oct((p.root / "events").stat().st_mode & 0o777) == "0o700"
        assert oct((p.root / "sessions").stat().st_mode & 0o777) == "0o700"
        assert oct(p.learner_md.stat().st_mode & 0o777) == "0o600"
        assert oct(p.review_queue.stat().st_mode & 0o777) == "0o600"


def test_init_idempotent_multiple_calls_preserves_data(tmp_path):
    p = AlvarPaths.for_project(tmp_path)
    p.init()
    p.learner_md.write_text("custom learner profile")
    p.events_file(SID).write_text('{"seq": 1}\n')
    p.session_file(SID).write_text("# Custom Session Content\n")

    for _ in range(5):
        p.init()

    assert p.learner_md.read_text() == "custom learner profile"
    assert p.events_file(SID).read_text() == '{"seq": 1}\n'
    assert p.session_file(SID).read_text() == "# Custom Session Content\n"


def test_path_helpers_resolution_and_properties(tmp_path):
    p = AlvarPaths.for_project(tmp_path)
    assert p.project_root == tmp_path.resolve()
    assert p.alvar_dir == p.root
    assert p.events_dir() == p.root / "events"
    assert p.sessions_dir() == p.root / "sessions"
    assert p.maps_dir() == p.root / "maps"
    assert p.visuals_dir() == p.root / "visuals"
    assert p.cache_dir() == p.root / "cache"
    assert p.sources_cache_dir() == p.root / "cache" / "sources"
    assert p.learner_md == p.root / "LEARNER.md"
    assert p.review_queue == p.root / "review-queue.json"
    assert p.events_file(SID) == p.root / "events" / f"{SID}.jsonl"
    assert p.session_file(SID) == p.root / "sessions" / f"{SID}.md"
    assert p.session_lock_file(SID) == p.root / "sessions" / f"{SID}.lock"
    assert p.map_file("Quantum Computing") == p.root / "maps" / "quantum-computing.md"

    # All path helpers provably remain inside .alvar/
    helpers = [
        p.alvar_dir,
        p.events_dir(),
        p.sessions_dir(),
        p.maps_dir(),
        p.visuals_dir(),
        p.cache_dir(),
        p.sources_cache_dir(),
        p.learner_md,
        p.review_queue,
        p.events_file(SID),
        p.session_file(SID),
        p.session_lock_file(SID),
        p.map_file("Quantum Computing"),
    ]
    for h in helpers:
        assert h.is_relative_to(p.root)


@pytest.mark.parametrize(
    "bad", ["../../etc/passwd", "a/b", "", "X" * 5, "2026-01-01-topic-ZZZZZZ", "2026-01-01-x-abc123/../.."]
)
def test_bad_session_ids_rejected(paths, bad):
    with pytest.raises(ValueError):
        paths.events_file(bad)
    with pytest.raises(ValueError):
        paths.session_file(bad)
    with pytest.raises(ValueError):
        paths.session_lock_file(bad)
    with pytest.raises(ValueError):
        paths.session_lock(bad)


def test_slugify_strips_traversal():
    assert slugify("../../Etc/Passwd!!") == "etc-passwd"
    with pytest.raises(ValueError):
        slugify("///")


def test_map_file_stays_inside_root(paths):
    assert paths.map_file("../../x").is_relative_to(paths.root)


def test_safe_escapes_rejected(paths):
    with pytest.raises(UnsafePathError):
        paths._safe("../outside")
    with pytest.raises(UnsafePathError):
        paths._safe("events", "../../outside")
    with pytest.raises(UnsafePathError):
        paths._safe("/abs/path")


@pytest.mark.skipif(os.name != "posix", reason="symlinks need privileges on Windows")
def test_symlinked_dir_is_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    p = AlvarPaths.for_project(proj)
    p.init()
    (p.root / "events").rmdir()
    (p.root / "events").symlink_to(outside)
    with pytest.raises(UnsafePathError):
        p.events_dir()


@pytest.mark.skipif(os.name != "posix", reason="symlinks need privileges on Windows")
def test_symlinked_root_is_refused(tmp_path):
    (tmp_path / "real").mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".alvar").symlink_to(tmp_path / "real")
    with pytest.raises(UnsafePathError):
        AlvarPaths.for_project(proj).init()


def test_session_lock_basic_acquire_release(paths):
    lock = paths.session_lock(SID)
    assert not lock.is_locked
    with lock:
        assert lock.is_locked
        assert paths.session_lock_file(SID).exists()
    assert not lock.is_locked


def test_session_lock_prevents_multiprocess_write_collision(tmp_path):
    p = AlvarPaths.for_project(tmp_path)
    p.init()

    ctx = mp.get_context("spawn")
    ready_event = ctx.Event()
    stop_event = ctx.Event()

    holder = ctx.Process(target=_lock_holder_worker, args=(p.root, SID, ready_event, stop_event))
    holder.start()

    try:
        assert ready_event.wait(timeout=10), "Lock holder process did not acquire lock in time"

        # Another process attempting to acquire the same session lock must fail
        result_queue = ctx.Queue()
        contender = ctx.Process(target=_contending_worker, args=(p.root, SID, result_queue))
        contender.start()
        contender.join(timeout=5)
        outcome = result_queue.get(timeout=2)
        assert outcome == "locked", f"Expected 'locked' but got {outcome}"

        # A different session ID can be locked concurrently without conflict
        with p.session_lock(OTHER_SID, timeout=0.0) as other_lock:
            assert other_lock.is_locked

    finally:
        stop_event.set()
        holder.join(timeout=5)

    # After the holder process releases the lock, acquiring it succeeds
    with p.session_lock(SID, timeout=1.0) as acquired_lock:
        assert acquired_lock.is_locked


def test_session_lock_serializes_concurrent_process_writes(tmp_path):
    p = AlvarPaths.for_project(tmp_path)
    p.init()
    p.session_file(SID).write_text("")

    ctx = mp.get_context("spawn")
    p1 = ctx.Process(target=_serial_writer_worker, args=(p.root, SID, "AAA\n"))
    p2 = ctx.Process(target=_serial_writer_worker, args=(p.root, SID, "BBB\n"))

    p1.start()
    p2.start()
    p1.join(timeout=10)
    p2.join(timeout=10)

    content = p.session_file(SID).read_text(encoding="utf-8")
    lines = sorted(content.strip().splitlines())
    assert lines == ["AAA", "BBB"], f"Expected serialized writes but got {content!r}"
