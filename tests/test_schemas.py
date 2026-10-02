import pytest

from modules.schema_check import SCHEMA_DIR, SchemaError, schema_names, validate
from modules.state.states import State

GOOD_NODE = {
    "node_id": "forms.pullback",
    "label": "Pullback",
    "prerequisites": ["forms.covector"],
    "teaches": ["definition"],
    "misconception_tags": ["pullback-not-pushforward"],
    "quiz_blueprint": {"recall": 1, "application": 1},
    "sources": [],
}


def test_all_schemas_are_valid_and_loadable():
    assert set(schema_names()) == {"answer_record", "event", "fsrs_card", "node_contract", "review_queue", "verdict"}


def test_event_state_enum_matches_State_enum():
    import json

    s = json.loads((SCHEMA_DIR / "event.schema.json").read_text())
    assert set(s["properties"]["to"]["enum"]) == {x.value for x in State}


def test_node_contract_ok_and_rejects_missing_application_item():
    validate("node_contract", GOOD_NODE)
    bad = {**GOOD_NODE, "quiz_blueprint": {"recall": 1}}
    with pytest.raises(SchemaError):
        validate("node_contract", bad)


def test_node_contract_rejects_unknown_field_and_bad_id():
    with pytest.raises(SchemaError):
        validate("node_contract", {**GOOD_NODE, "extra": 1})
    with pytest.raises(SchemaError):
        validate("node_contract", {**GOOD_NODE, "node_id": "../etc/passwd"})


def test_confirmed_verdict_needs_two_citations():
    cit = {"url": "https://a.org", "quote": "q", "retrieved_at": "2026-01-01T00:00:00Z"}
    base = {"verdict": "confirmed", "confidence": 0.9, "checked_at": "2026-01-01T00:00:00Z"}
    with pytest.raises(SchemaError):
        validate("verdict", {**base, "citations": [cit]})
    validate("verdict", {**base, "citations": [cit, {**cit, "url": "https://b.org"}]})
    validate("verdict", {"verdict": "unknown", "confidence": 0, "citations": [], "checked_at": "2026-01-01T00:00:00Z"})


def test_verdict_rejects_non_http_urls():
    cit = {"url": "javascript:alert(1)", "quote": "q", "retrieved_at": "2026-01-01T00:00:00Z"}
    with pytest.raises(SchemaError):
        validate(
            "verdict",
            {"verdict": "qualified", "confidence": 0.5, "citations": [cit], "checked_at": "2026-01-01T00:00:00Z"},
        )


def test_answer_record():
    rec = {
        "question_id": "q-17",
        "node_id": "forms.pullback",
        "selected": "B",
        "correct": False,
        "confidence": "high",
        "response_time_ms": 8200,
        "misconception_tag": "pullback-not-pushforward",
    }
    validate("answer_record", rec)
    with pytest.raises(SchemaError):
        validate("answer_record", {**rec, "response_time_ms": -1})
    with pytest.raises(SchemaError):
        validate("answer_record", {**rec, "selected": "Z"})


def test_fsrs_card_bounds():
    card = {
        "node_id": "forms.pullback",
        "stability": 8.4,
        "difficulty": 5.8,
        "due_at": "2026-04-12T10:00:00Z",
        "last_rating": "good",
        "reps": 4,
        "lapses": 1,
    }
    validate("fsrs_card", card)
    with pytest.raises(SchemaError):
        validate("fsrs_card", {**card, "difficulty": 11})
    validate("review_queue", {"version": 1, "cards": [card]})
    with pytest.raises(SchemaError):
        validate("review_queue", {"version": 1, "cards": [{**card, "reps": -1}]})


def test_unknown_schema_name():
    with pytest.raises(SchemaError):
        validate("nope", {})
