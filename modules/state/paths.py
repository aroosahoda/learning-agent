"""The .alvar/ folder: creation and safe path resolution (Phase 1.2)."""

from __future__ import annotations

import json
import os
import re
import types
from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock, Timeout

from modules.schema_check import validate
from modules.state.atomic import atomic_write_json, atomic_write_text

SUBDIRS = ("maps", "sessions", "events", "visuals", "cache/sources")
SESSION_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]{1,60}-[0-9a-f]{6}$")
_NON_SLUG = re.compile(r"[^a-z0-9]+")
_LEARNER_STUB = (
    "# Learner profile\n\n<!-- Populated in Phase 2.3. Ground truths, pace, voice, known misconceptions. -->\n"
)


class UnsafePathError(ValueError):
    """A path escaped .alvar/ or traverses a symlink."""


class SessionLockError(RuntimeError):
    """A session is locked by another process."""


def slugify(text: str, max_len: int = 60) -> str:
    slug = _NON_SLUG.sub("-", text.strip().lower()).strip("-")[:max_len].strip("-")
    if not slug:
        raise ValueError("name has no usable characters (need a-z or 0-9)")
    return slug


class SessionLock:
    """Advisory session lock across processes."""

    def __init__(self, lock_path: Path, session_id: str, timeout: float = 0.0) -> None:
        self.lock_path = lock_path
        self.session_id = session_id
        self.timeout = timeout
        self._lock = FileLock(str(lock_path), timeout=timeout, is_singleton=True)

    def acquire(self, timeout: float | None = None) -> None:
        t = self.timeout if timeout is None else timeout
        try:
            self._lock.acquire(timeout=t)
        except Timeout as e:
            raise SessionLockError(
                f"session {self.session_id} is locked by another process (lock file: {self.lock_path})"
            ) from e

    def release(self) -> None:
        self._lock.release()

    @property
    def is_locked(self) -> bool:
        return bool(self._lock.is_locked)

    def __enter__(self) -> SessionLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self.release()


@dataclass(frozen=True)
class AlvarPaths:
    root: Path  # absolute, resolved path of the .alvar directory

    @classmethod
    def for_project(cls, project_dir: Path | str = ".") -> AlvarPaths:
        return cls(Path(project_dir).resolve() / ".alvar")

    @property
    def project_root(self) -> Path:
        """The root directory of the project enclosing .alvar/."""
        return self.root.parent

    @property
    def alvar_dir(self) -> Path:
        """The .alvar directory."""
        return self.root

    # -- safety ---------------------------------------------------------
    def _safe(self, *parts: str) -> Path:
        candidate = self.root.joinpath(*parts)
        cur = self.root
        if cur.is_symlink():
            raise UnsafePathError(f"{cur} is a symlink")
        for part in parts:
            for piece in Path(part).parts:
                if piece in ("", "."):
                    continue
                cur = cur / piece
                if cur.is_symlink():
                    raise UnsafePathError(f"{cur} is a symlink")
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.root):
            raise UnsafePathError(f"{candidate} escapes {self.root}")
        if resolved.is_symlink() or candidate.is_symlink():
            raise UnsafePathError(f"{candidate} is a symlink")
        return resolved

    # -- well-known locations ------------------------------------------
    @property
    def learner_md(self) -> Path:
        return self._safe("LEARNER.md")

    @property
    def review_queue(self) -> Path:
        return self._safe("review-queue.json")

    def events_dir(self) -> Path:
        return self._safe("events")

    def sessions_dir(self) -> Path:
        return self._safe("sessions")

    def maps_dir(self) -> Path:
        return self._safe("maps")

    def visuals_dir(self) -> Path:
        return self._safe("visuals")

    def cache_dir(self) -> Path:
        return self._safe("cache")

    def sources_cache_dir(self) -> Path:
        return self._safe("cache", "sources")

    def events_file(self, session_id: str) -> Path:
        return self._safe("events", f"{self._check_session_id(session_id)}.jsonl")

    def session_file(self, session_id: str) -> Path:
        return self._safe("sessions", f"{self._check_session_id(session_id)}.md")

    def session_lock_file(self, session_id: str) -> Path:
        return self._safe("sessions", f"{self._check_session_id(session_id)}.lock")

    def map_file(self, topic: str) -> Path:
        return self._safe("maps", f"{slugify(topic)}.md")

    def session_lock(self, session_id: str, timeout: float = 0.0) -> SessionLock:
        """Create a cross-process session lock.

        Usage:
            with paths.session_lock(session_id):
                # Drive session safely
        """
        sid = self._check_session_id(session_id)
        lock_file = self.session_lock_file(sid)
        lock_file.parent.mkdir(mode=0o700, exist_ok=True)
        return SessionLock(lock_file, sid, timeout=timeout)

    @staticmethod
    def _check_session_id(session_id: str) -> str:
        if not SESSION_ID_RE.fullmatch(session_id):
            raise ValueError(f"invalid session id: {session_id!r}")
        return session_id

    # -- lifecycle ------------------------------------------------------
    def init(self) -> None:
        """Idempotent: creates missing pieces, never overwrites existing data."""
        if self.root.is_symlink():
            raise UnsafePathError(f"{self.root} is a symlink")
        self.root.mkdir(mode=0o700, exist_ok=True)
        for sub in SUBDIRS:
            self._safe(*sub.split("/"))  # symlink / escape check before creating
            cur = self.root
            for part in sub.split("/"):  # mkdir(parents=True) ignores mode for parents
                cur = cur / part
                cur.mkdir(mode=0o700, exist_ok=True)
        if not self.learner_md.exists():
            atomic_write_text(self.learner_md, _LEARNER_STUB)
        if not self.review_queue.exists():
            atomic_write_json(self.review_queue, {"version": 1, "cards": []})
        validate("review_queue", json.loads(self.review_queue.read_text(encoding="utf-8")))
        if os.name == "posix":
            os.chmod(self.root, 0o700)
            for sub in SUBDIRS:
                cur = self.root
                for part in sub.split("/"):
                    cur = cur / part
                    os.chmod(cur, 0o700)
            if self.learner_md.exists():
                os.chmod(self.learner_md, 0o600)
            if self.review_queue.exists():
                os.chmod(self.review_queue, 0o600)
        else:
            os.chmod(self.root, 0o700)
