"""Tests for the eval's scoring functions and the question file. No network."""

import json
from pathlib import Path

from evals.run_eval import contains_fact, has_expected_facts, is_correct, is_refusal

QUESTIONS_FILE = Path(__file__).resolve().parent.parent / "evals" / "questions.jsonl"


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
