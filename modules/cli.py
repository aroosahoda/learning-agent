"""Tiny CLI: `python -m modules.cli init|start|resume|validate`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from modules.config import ConfigError, load_config
from modules.schema_check import SchemaError, schema_names, validate
from modules.state.events import CorruptLogError, read_events
from modules.state.paths import AlvarPaths
from modules.state.session import Session, SessionError, replay


def cmd_validate(paths: AlvarPaths, cfg_path: Path) -> int:
    problems: list[str] = []
    try:
        load_config(cfg_path)
    except ConfigError as e:
        problems.append(f"config: {e}")
    if paths.root.exists():
        import json

        try:
            validate("review_queue", json.loads(paths.review_queue.read_text(encoding="utf-8")))
        except (SchemaError, ValueError, OSError) as e:
            problems.append(f"review-queue.json: {e}")
        for f in sorted(paths.events_dir().glob("*.jsonl")):
            try:
                replay(read_events(f, f.stem))
            except (CorruptLogError, ValueError) as e:
                problems.append(f"events/{f.name}: {e}")
    for p in problems:
        print("PROBLEM:", p, file=sys.stderr)
    print(f"schemas: {', '.join(schema_names())}")
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="alvar")
    ap.add_argument("--project", default=".", help="project directory that holds .alvar/")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("validate")
    s = sub.add_parser("start")
    s.add_argument("topic")
    r = sub.add_parser("resume")
    r.add_argument("session_id", nargs="?")
    a = ap.parse_args(argv)

    project = Path(a.project).resolve()
    paths = AlvarPaths.for_project(project)
    cfg_path = project / "config.toml"
    try:
        if a.cmd == "validate":
            return cmd_validate(paths, cfg_path)
        cfg = load_config(cfg_path)
        if a.cmd == "init":
            paths.init()
            print(f"initialised {paths.root}")
        elif a.cmd == "start":
            sess = Session.start(paths, a.topic, cfg)
            print(f"started {sess.snapshot.session_id} in state {sess.snapshot.state.value}")
        elif a.cmd == "resume":
            sid = a.session_id or Session.find_resumable(paths)
            if not sid:
                print("no resumable session", file=sys.stderr)
                return 1
            sess = Session.resume(paths, sid, cfg)
            print(f"resumed {sid} at state {sess.snapshot.state.value} (seq {sess.snapshot.last_seq})")
    except (ConfigError, SessionError, CorruptLogError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
