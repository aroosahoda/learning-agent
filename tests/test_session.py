import pytest

from modules.state.events import CorruptLogError
from modules.state.session import Session, SessionError, replay
from modules.state.states import State


def test_start_creates_log_and_markdown_stub(paths, cfg):
    s = Session.start(paths, "Differential Forms", cfg)
    assert s.snapshot.state is State.GREET and s.snapshot.last_seq == 1
    assert paths.events_file(s.snapshot.session_id).exists()
    assert paths.session_file(s.snapshot.session_id).read_text().startswith("---\nsession:")


def test_topic_cannot_inject_frontmatter(paths, cfg):
    s = Session.start(paths, 'x" admin: true --- y', cfg)
    md = paths.session_file(s.snapshot.session_id).read_text()
    front = md.split("---\n")[1]
    assert front.count("\n") == 2  # exactly: session + topic
    assert front.splitlines()[1].startswith('topic: "')  # value stays one quoted string


@pytest.mark.parametrize("topic", ["", "   ", "a" * 201, "bad\x00topic", "line\nbreak"])
def test_bad_topics_rejected(paths, cfg, topic):
    with pytest.raises(SessionError):
        Session.start(paths, topic, cfg)


def test_resume_restores_state_and_logs_resume(paths, cfg):
    s = Session.start(paths, "topic", cfg)
    s.record_transition(State.PLAN)
    s.record_transition(State.TEACH)
    r = Session.resume(paths, s.snapshot.session_id, cfg)
    assert r.snapshot.state is State.TEACH
    assert r.log.read()[-1]["event"] == "session_resumed"


def test_ended_session_cannot_be_resumed_and_find_skips_it(paths, cfg):
    a = Session.start(paths, "aaa", cfg)
    a.end()
    with pytest.raises(SessionError):
        Session.resume(paths, a.snapshot.session_id, cfg)
    assert Session.find_resumable(paths) is None
    b = Session.start(paths, "bbb", cfg)
    assert Session.find_resumable(paths) == b.snapshot.session_id


def test_find_resumable_skips_corrupt_logs(paths, cfg):
    s = Session.start(paths, "topic", cfg)
    paths.events_file(s.snapshot.session_id).write_text("garbage\n")
    assert Session.find_resumable(paths) is None


def test_resume_unknown_or_malicious_id(paths, cfg):
    with pytest.raises(SessionError):
        Session.resume(paths, "2026-09-28-nothing-abcdef", cfg)
    with pytest.raises(ValueError):
        Session.resume(paths, "../../../etc/passwd", cfg)


def test_replay_rejects_event_after_end_and_missing_start():
    base = {"t": "2026-01-01T00:00:00Z", "session": "2026-01-01-x-abcdef"}
    start = {**base, "event": "session_started", "seq": 1, "topic": "x"}
    end = {**base, "event": "session_ended", "seq": 2, "reason": "completed"}
    late = {**base, "event": "checkpoint", "seq": 3, "state": "GREET"}
    with pytest.raises(CorruptLogError):
        replay([start, end, late])
    with pytest.raises(CorruptLogError):
        replay([end])


def test_session_refuses_to_write_on_top_of_corruption_or_after_end(paths, cfg):
    s = Session.start(paths, "topic", cfg)
    f = paths.events_file(s.snapshot.session_id)
    good = f.read_text()
    f.write_text("garbage\n" + good)
    before = f.read_bytes()
    with pytest.raises(CorruptLogError):
        s.checkpoint("x")
    assert f.read_bytes() == before  # nothing appended
    f.write_text(good)
    other = Session.resume(paths, s.snapshot.session_id, cfg)
    other.end()
    with pytest.raises(SessionError):  # stale handle must not write after end
        s.checkpoint("late")
