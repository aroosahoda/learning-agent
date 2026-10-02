"""The .alvar/ folder: creation and safe path resolution (Phase 1.2)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

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


def slugify(text: str, max_len: int = 60) -> str:
    slug = _NON_SLUG.sub("-", text.strip().lower()).strip("-")[:max_len].strip("-")
    if not slug:
        raise ValueError("name has no usable characters (need a-z or 0-9)")
    return slug


@dataclass(frozen=True)
class AlvarPaths:
    root: Path  # absolute, resolved path of the .alvar directory

    @classmethod
    def for_project(cls, project_dir: Path | str = ".") -> AlvarPaths:
        return cls(Path(project_dir).resolve() / ".alvar")

    # -- safety ---------------------------------------------------------
    def _safe(self, *parts: str) -> Path:
        candidate = self.root.joinpath(*parts)
        cur = self.root
        if cur.is_symlink():
            raise UnsafePathError(f"{cur} is a symlink")
        for part in parts:
            cur = cur / part
            if cur.is_symlink():
                raise UnsafePathError(f"{cur} is a symlink")
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.root):
            raise UnsafePathError(f"{candidate} escapes {self.root}")
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

    def events_file(self, session_id: str) -> Path:
        return self._safe("events", f"{self._check_session_id(session_id)}.jsonl")

    def session_file(self, session_id: str) -> Path:
        return self._safe("sessions", f"{self._check_session_id(session_id)}.md")

    def map_file(self, topic: str) -> Path:
        return self._safe("maps", f"{slugify(topic)}.md")

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
        os.chmod(self.root, 0o700)
