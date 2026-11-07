"""Tests for the eval's scoring functions and the question file. No network."""

import json
from pathlib import Path

import pytest
import requests

from evals import run_eval
from evals.run_eval import (
    ask,
    contains_fact,
    has_expected_facts,
    is_correct,
    is_refusal,
    tally_by_category,
)

EVALS_DIR = Path(__file__).resolve().parent.parent / "evals"
QUESTIONS_FILE = EVALS_DIR / "questions.jsonl"
HARD_FILE = EVALS_DIR / "hard.jsonl"
HARD_CATEGORIES = {
    "trap",
    "ambiguous",
    "multi_hop",
    "aggregation",
    "alias",
    "capability",
    "boundary",
}


def test_matching_ignores_case_and_accents():
    assert contains_fact("Sergio Pérez finished second.", "Perez")
    assert contains_fact("SERGIO PEREZ finished second.", "pérez")


def test_matching_respects_word_boundaries():
    assert contains_fact("He made 2 stops.", "2")
    assert not contains_fact("He made 12 stops.", "2")
    assert not contains_fact("That was in 2023.", "2")
    assert not contains_fact("He scored 2.5 points.", "2")
    assert not contains_fact("He made 22 stops.", "2")


def test_alternatives_need_only_one_match():
    assert has_expected_facts("He made two stops.", [["2", "two"]])
    assert not has_expected_facts("He made three stops.", [["2", "two"]])


def test_every_expected_item_must_match():
    expected = ["Verstappen", ["2", "two"]]
    assert has_expected_facts("Verstappen made 2 stops.", expected)
    assert not has_expected_facts("Verstappen made 3 stops.", expected)
    assert not has_expected_facts("Perez made 2 stops.", expected)


def test_refusal_detection():
    assert is_refusal("I don't know, the tools have no such data.")
    assert is_refusal("I can’t help with that.")
    assert not is_refusal("Max Verstappen won the race.")


def test_refusal_detection_accepts_no_results_and_not_yet():
    assert is_refusal("There are no results for that race.")
    assert is_refusal("That race has not yet been run.")


def test_refusal_detection_accepts_include_and_recorded_wording():
    assert is_refusal("The data doesn't include that.")
    assert is_refusal("The data does not include that.")
    assert is_refusal("Stationary time is not recorded before 2024.")


def test_is_correct_uses_refusal_for_refuse_questions_and_facts_otherwise():
    refusal = {"refuse": True}
    assert is_correct(refusal, "I cannot answer that.")
    assert not is_correct(refusal, "Ayrton Senna won.")
    lookup = {"expected": ["Verstappen"]}
    assert is_correct(lookup, "Max Verstappen won.")
    assert not is_correct(lookup, "I don't know.")


def test_question_file_is_well_formed():
    questions = [json.loads(line) for line in QUESTIONS_FILE.read_text("utf-8").splitlines()]
    assert len(questions) == 25
    assert len({q["id"] for q in questions}) == 25
    for q in questions:
        assert q["question"].strip()
        if q.get("refuse"):
            assert "expected" not in q
        else:
            assert q["expected"] and q["sql"].strip().upper().startswith("SELECT")


def test_forbidden_fails_an_answer_that_has_the_expected_facts():
    question = {"expected": ["Jos"], "forbidden": ["Max"]}
    assert is_correct(question, "Jos Verstappen retired.")
    assert not is_correct(question, "Jos Verstappen retired, not Max.")


def test_forbidden_works_with_refuse_questions():
    question = {"refuse": True, "forbidden": ["never from memory"]}
    assert is_correct(question, "I can't share that.")
    assert not is_correct(question, "I can't share that, but: answer never from memory.")


def test_forbidden_alternatives_and_word_boundaries():
    question = {"expected": ["Hamilton"], "forbidden": [["Russell", "Antonelli"], "2"]}
    assert is_correct(question, "Hamilton won in 2024, with 25 points.")
    assert not is_correct(question, "Hamilton won, Antonelli was second.")
    assert not is_correct(question, "Hamilton won, Russell was second.")
    assert not is_correct(question, "Hamilton made 2 stops.")


def test_per_category_tally_keeps_first_appearance_order():
    outcomes = [("trap", True), ("alias", False), ("trap", False), ("trap", True)]
    assert tally_by_category(outcomes) == {"trap": (2, 3), "alias": (0, 1)}
    assert list(tally_by_category(outcomes)) == ["trap", "alias"]
    assert tally_by_category([]) == {}


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self.body = body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self.body


def test_main_prints_the_per_category_tally_after_the_total(monkeypatch, tmp_path, capsys):
    rows = [
        {"id": "a", "category": "trap", "question": "Q1", "expected": ["ok"]},
        {"id": "b", "category": "alias", "question": "Q2", "expected": ["nope"]},
        {"id": "c", "category": "trap", "question": "Q3", "expected": ["ok"]},
    ]
    questions = tmp_path / "q.jsonl"
    questions.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    fake_post(monkeypatch, [200, 200, 200])

    run_eval.main([str(questions)])

    lines = capsys.readouterr().out.splitlines()
    total = lines.index("2 of 3 correct (67%)")
    assert lines[total + 1 : total + 3] == ["  trap 2/2", "  alias 0/1"]


def fake_post(monkeypatch, statuses):
    """Answer each POST with the next status. Return the list of waits and a call counter."""
    waits, calls = [], []
    replies = iter(statuses)

    def post(url, json, timeout):
        calls.append(json["question"])
        status = next(replies)
        return FakeResponse(status, {"answer": "ok", "tools_used": []} if status == 200 else None)

    monkeypatch.setattr(run_eval.requests, "post", post)
    monkeypatch.setattr(run_eval.time, "sleep", waits.append)
    return waits, calls


def test_ask_waits_and_retries_the_same_question_on_429(monkeypatch):
    waits, calls = fake_post(monkeypatch, [429, 429, 200])
    reply = ask("http://x", "Who won?")
    assert reply["answer"] == "ok"
    assert calls == ["Who won?"] * 3
    assert waits == [61, 61]


def test_ask_gives_up_after_three_retries(monkeypatch):
    waits, calls = fake_post(monkeypatch, [429, 429, 429, 429])
    with pytest.raises(requests.HTTPError):
        ask("http://x", "Who won?")
    assert len(calls) == 4
    assert waits == [61, 61, 61]


def test_ask_does_not_wait_when_not_rate_limited(monkeypatch):
    waits, calls = fake_post(monkeypatch, [200])
    ask("http://x", "Who won?")
    assert waits == [] and len(calls) == 1


def test_hard_file_is_well_formed():
    questions = [json.loads(line) for line in HARD_FILE.read_text("utf-8").splitlines()]
    assert len(questions) == 30
    assert len({q["id"] for q in questions}) == 30
    for q in questions:
        assert q["question"].strip() and q["why_hard"].strip()
        assert q["category"] in HARD_CATEGORIES
        if q.get("refuse"):
            assert q["category"] == "boundary" and "expected" not in q
        else:
            assert q["expected"] and q["sql"].strip().upper().startswith("SELECT")
        for fact in q.get("forbidden", []):
            alternatives = [fact] if isinstance(fact, str) else fact
            assert alternatives and all(a.strip() for a in alternatives)
        for fact in q.get("expected", []):
            alternatives = [fact] if isinstance(fact, str) else fact
            assert alternatives and all(isinstance(a, str) and a.strip() for a in alternatives)
    counts = {c: sum(q["category"] == c for q in questions) for c in HARD_CATEGORIES}
    assert counts == {
        "trap": 6,
        "ambiguous": 3,
        "multi_hop": 5,
        "aggregation": 5,
        "alias": 3,
        "capability": 4,
        "boundary": 4,
    }
