import os

import pytest

from modules.state.paths import AlvarPaths, UnsafePathError, slugify


def test_init_creates_layout_idempotently_and_private(tmp_path):
    p = AlvarPaths.for_project(tmp_path)
    p.init()
    p.learner_md.write_text("keep me")
    p.init()
    assert p.learner_md.read_text() == "keep me"
    for sub in ("maps", "sessions", "events", "visuals", "cache/sources", "cache"):
        assert (p.root / sub).is_dir()
    if os.name == "posix":
        assert oct((p.root / "cache").stat().st_mode & 0o777) == "0o700"
        assert oct(p.root.stat().st_mode & 0o777) == "0o700"


@pytest.mark.parametrize(
    "bad", ["../../etc/passwd", "a/b", "", "X" * 5, "2026-01-01-topic-ZZZZZZ", "2026-01-01-x-abc123/../.."]
)
def test_bad_session_ids_rejected(paths, bad):
    with pytest.raises(ValueError):
        paths.events_file(bad)


def test_slugify_strips_traversal():
    assert slugify("../../Etc/Passwd!!") == "etc-passwd"
    with pytest.raises(ValueError):
        slugify("///")


def test_map_file_stays_inside_root(paths):
    assert paths.map_file("../../x").is_relative_to(paths.root)


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
