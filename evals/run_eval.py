"""Accuracy eval: asks every question in a file through POST /ask and prints a score.

Usage:
    uv run python evals/run_eval.py [QUESTIONS_FILE] [--url http://localhost:8000]

QUESTIONS_FILE defaults to evals/questions.jsonl. It has one JSON object per line.

A question with known facts:
    {"id": "q01", "category": "lookup", "question": "Who won Monza 2023?",
     "expected": ["Verstappen"], "sql": "SELECT ..."}

    "expected" is a list of facts that must ALL appear in the answer. Each fact is a string,
    or a list of alternatives where any one is enough, e.g. [["2", "two"], "Verstappen"].
    "sql" is the query that produced the facts, so anyone can recheck them.

A question the analyst should refuse (off topic, future, no data):
    {"id": "q22", "category": "refusal", "question": "...", "refuse": true}

    It passes when the answer contains a refusal phrase such as "don't know" or "cannot".

Either kind of question can also have "forbidden": facts in the same format as "expected",
where NONE may appear in the answer, or the question fails. Use it only for facts a correct
answer would never say, e.g. "Max" in a question about Jos Verstappen.

The API allows 5 questions a minute per IP. On HTTP 429 the runner waits 61 seconds and asks
the same question again, up to 3 times.

Matching ignores case and accents ("Perez" matches "Pérez") and respects word boundaries,
so "2" does not match "12" or "2023".

Every score should be recorded with the model name and date printed on the last lines.
"""

import argparse
import datetime
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

REQUEST_TIMEOUT_SECONDS = 180
ANSWER_PREVIEW_CHARS = 300
RATE_LIMIT_WAIT_SECONDS = 61
RATE_LIMIT_RETRIES = 3
REFUSAL_PHRASES = [
    "don't know",
    "do not know",
    "don't have",
    "can't",
    "cannot",
    "unable",
    "not able",
    "no data",
    "not available",
    "only answer",
    "no results",
    "not yet",
    "doesn't include",
    "does not include",
    "not recorded",
]


def normalize(text: str) -> str:
    """Lowercase, drop accents and use plain apostrophes, so comparisons are forgiving."""
    decomposed = unicodedata.normalize("NFKD", text.replace("’", "'"))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def contains_fact(answer: str, fact: str) -> bool:
    """True if fact appears as a whole word or number ('2' is not in '12', '2023' or '2.5')."""
    pattern = r"(?<!\w)" + re.escape(normalize(fact)) + r"(?!\w)(?!\.\d)"
    return re.search(pattern, normalize(answer)) is not None


def has_expected_facts(answer: str, expected: list) -> bool:
    """Every item must match. An item that is a list matches when any alternative does."""
    for item in expected:
        alternatives = [item] if isinstance(item, str) else item
        if not any(contains_fact(answer, alternative) for alternative in alternatives):
            return False
    return True


def has_forbidden_facts(answer: str, forbidden: list) -> bool:
    """True if ANY forbidden item (or any alternative inside one) appears in the answer."""
    for item in forbidden:
        alternatives = [item] if isinstance(item, str) else item
        if any(contains_fact(answer, alternative) for alternative in alternatives):
            return True
    return False


def is_refusal(answer: str) -> bool:
    text = normalize(answer)
    return any(phrase in text for phrase in REFUSAL_PHRASES)


def is_correct(question: dict, answer: str) -> bool:
    if has_forbidden_facts(answer, question.get("forbidden", [])):
        return False
    if question.get("refuse"):
        return is_refusal(answer)
    return has_expected_facts(answer, question["expected"])


def tally_by_category(outcomes: list[tuple[str, bool]]) -> dict[str, tuple[int, int]]:
    """Map each category (in order of first appearance) to (passed, asked)."""
    tally: dict[str, tuple[int, int]] = {}
    for category, passed in outcomes:
        correct, asked = tally.get(category, (0, 0))
        tally[category] = (correct + passed, asked + 1)
    return tally


def load_questions(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def ask(url: str, question: str) -> dict:
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        response = requests.post(
            f"{url}/ask", json={"question": question}, timeout=REQUEST_TIMEOUT_SECONDS
        )
        if response.status_code != 429 or attempt == RATE_LIMIT_RETRIES:
            break
        print(f"     rate limited, waiting {RATE_LIMIT_WAIT_SECONDS}s", flush=True)
        time.sleep(RATE_LIMIT_WAIT_SECONDS)
    response.raise_for_status()
    return response.json()


def format_tools(tools_used: list[dict]) -> str:
    return ", ".join(f"{t['name']}({json.dumps(t['input'])})" for t in tools_used) or "none"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score the analyst on a file of questions.")
    parser.add_argument("questions_file", nargs="?", default="evals/questions.jsonl")
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args(argv)

    # Answers can contain accents that a Windows console cannot print.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # Run as a script, only evals/ is on the path, so add the repo root to import app.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.analyst import MODEL

    questions = load_questions(Path(args.questions_file))
    correct = 0
    outcomes = []
    for q in questions:
        try:
            reply = ask(args.url, q["question"])
            answer, tools_used = reply["answer"], reply["tools_used"]
            passed = is_correct(q, answer)
        except (requests.RequestException, ValueError, KeyError) as error:
            answer, tools_used, passed = f"request failed: {error}", [], False
        correct += passed
        outcomes.append((q.get("category", "uncategorized"), passed))
        print(f"{'PASS' if passed else 'FAIL'} {q['id']} {q['question']}", flush=True)
        print(f"     answer: {' '.join(answer.split())[:ANSWER_PREVIEW_CHARS]}")
        print(f"     tools: {format_tools(tools_used)}")

    percent = round(100 * correct / len(questions)) if questions else 0
    print(f"\n{correct} of {len(questions)} correct ({percent}%)")
    for category, (passed, asked) in tally_by_category(outcomes).items():
        print(f"  {category} {passed}/{asked}")
    print(f"model: {MODEL}  date: {datetime.date.today().isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
