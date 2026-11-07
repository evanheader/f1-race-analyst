"""Tests for POST /ask. No network and no API key: Claude is replaced by a scripted fake."""

import datetime
import json
from types import SimpleNamespace

import anthropic
import httpx2 as httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import InternalError, ProgrammingError

from app import analyst, main
from app.database import get_read_only_db
from app.main import app, get_anthropic_client
from app.tools import TOOLS


class FakeClient:
    """Stands in for anthropic.Anthropic: returns scripted responses, records every call."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        kwargs["messages"] = list(kwargs["messages"])  # the loop keeps appending to its list
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def text_reply(words):
    return SimpleNamespace(
        stop_reason="end_turn", content=[SimpleNamespace(type="text", text=words)]
    )


def tool_block(id, name, **tool_input):
    return SimpleNamespace(type="tool_use", id=id, name=name, input=tool_input)


def tool_reply(*blocks):
    return SimpleNamespace(stop_reason="tool_use", content=list(blocks))


def monza_call(id):
    return tool_reply(tool_block(id, "get_race_results", season=2023, race="monza"))


@pytest.fixture
def ask(client, db):
    """Post a question with the given fake Claude. Returns (response, fake)."""
    app.dependency_overrides[get_read_only_db] = lambda: db

    def run(fake, question="Who won Monza 2023?"):
        app.dependency_overrides[get_anthropic_client] = lambda: fake
        return client.post("/ask", json={"question": question}), fake

    return run


@pytest.fixture
def monza(make_race, make_driver, make_result):
    race = make_race(
        season=2023,
        round=14,
        name="Italian Grand Prix",
        date=datetime.date(2023, 9, 3),
        circuit_ref="monza",
    )
    make_result(race, make_driver("max_verstappen", "VER", "Max Verstappen"), points=25)
    make_result(race, make_driver("perez", "PER", "Sergio Perez"), position=2, points=18)


def test_direct_answer_uses_no_tools(ask):
    response, fake = ask(FakeClient(text_reply("Hello.")))

    assert response.status_code == 200
    assert response.json() == {"answer": "Hello.", "tools_used": []}
    assert len(fake.calls) == 1


def test_request_carries_model_system_prompt_tools_and_the_question(ask):
    _, fake = ask(FakeClient(text_reply("ok")), question="  Who won?  ")

    call = fake.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["system"] == analyst.SYSTEM_PROMPT
    assert "never from memory" in call["system"]
    assert call["tools"] == TOOLS
    assert call["max_tokens"] > 0
    assert call["messages"] == [{"role": "user", "content": "Who won?"}]  # stripped


def test_one_tool_round_trip_with_real_tools(ask, monza):
    first = monza_call("t1")
    response, fake = ask(FakeClient(first, text_reply("Max Verstappen won.")))

    assert response.json() == {
        "answer": "Max Verstappen won.",
        "tools_used": [{"name": "get_race_results", "input": {"season": 2023, "race": "monza"}}],
    }
    sent_messages = fake.calls[1]["messages"]
    assert len(sent_messages) == 3
    assert sent_messages[1] == {"role": "assistant", "content": first.content}  # unchanged
    result = sent_messages[2]["content"][0]
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "t1"
    assert "is_error" not in result
    sent = json.loads(result["content"])
    assert sent["race"]["name"] == "Italian Grand Prix"
    assert [r["driver"] for r in sent["results"]] == ["Max Verstappen", "Sergio Perez"]


def test_tool_error_is_sent_back_with_is_error_and_the_loop_continues(ask, monza):
    bad = tool_reply(tool_block("t1", "get_race_results", season=2023, race="atlantis"))
    response, fake = ask(FakeClient(bad, monza_call("t2"), text_reply("Max Verstappen won.")))

    assert response.json()["answer"] == "Max Verstappen won."
    assert [t["input"]["race"] for t in response.json()["tools_used"]] == ["atlantis", "monza"]
    error_result = fake.calls[1]["messages"][-1]["content"][0]
    assert error_result["is_error"] is True
    assert "No race matching 'atlantis'" in json.loads(error_result["content"])["error"]
    assert "is_error" not in fake.calls[2]["messages"][-1]["content"][0]


def test_two_tool_calls_in_one_response_are_answered_in_one_message(ask, monza):
    both = tool_reply(
        tool_block("a", "get_race_results", season=2023, race="monza"),
        tool_block("b", "get_race_results", season=2023, race="14"),
    )
    response, fake = ask(FakeClient(both, text_reply("Same race.")))

    assert len(response.json()["tools_used"]) == 2
    assert len(fake.calls) == 2
    sent_messages = fake.calls[1]["messages"]
    assert len(sent_messages) == 3
    assert sent_messages[-1]["role"] == "user"
    assert [r["tool_use_id"] for r in sent_messages[-1]["content"]] == ["a", "b"]


def test_going_over_the_tool_call_limit_stops_with_the_fixed_answer(ask, monza):
    # 5 calls are allowed. The 6th is not run and nothing more is sent to Claude.
    response, fake = ask(FakeClient(*[monza_call(f"t{n}") for n in range(6)]))

    body = response.json()
    assert response.status_code == 200
    assert body["answer"] == analyst.TOO_COMPLEX_ANSWER
    assert "too complex" in body["answer"]
    assert len(body["tools_used"]) == 5
    assert len(fake.calls) == 6


def test_a_batch_that_would_cross_the_limit_is_not_run(ask, monza):
    pair = tool_reply(
        tool_block("x", "get_race_results", season=2023, race="monza"),
        tool_block("y", "get_race_results", season=2023, race="monza"),
    )
    response, _ = ask(FakeClient(*[monza_call(f"t{n}") for n in range(4)], pair))

    assert response.json()["answer"] == analyst.TOO_COMPLEX_ANSWER
    assert len(response.json()["tools_used"]) == 4


@pytest.mark.parametrize("key", [None, ""])
def test_missing_or_empty_key_gives_503(client, db, monkeypatch, key):
    app.dependency_overrides[get_read_only_db] = lambda: db
    if key is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", key)

    response = client.post("/ask", json={"question": "Who won?"})

    assert response.status_code == 503
    assert response.json() == {"detail": "The AI assistant is not configured."}


def test_the_client_is_built_once_with_a_timeout_and_retries(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    main._build_client.cache_clear()

    first, second = get_anthropic_client(), get_anthropic_client()

    assert first is second
    assert first.timeout == 30.0
    assert first.max_retries == 2
    main._build_client.cache_clear()


@pytest.mark.parametrize("question", ["", "   ", "x" * 501])
def test_empty_or_too_long_question_gives_422(ask, question):
    response, fake = ask(FakeClient(), question=question)

    assert response.status_code == 422
    assert fake.calls == []


def test_a_500_character_question_is_accepted(ask):
    response, _ = ask(FakeClient(text_reply("ok")), question="x" * 500)

    assert response.status_code == 200


def test_timeout_gives_504(ask):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response, _ = ask(FakeClient(anthropic.APITimeoutError(request=request)))

    assert response.status_code == 504
    assert response.json() == {"detail": "The AI assistant took too long to answer."}


def test_api_error_gives_502_without_leaking_details(ask):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    failure = anthropic.InternalServerError(
        "secret-details", response=httpx.Response(500, request=request), body=None
    )
    response, _ = ask(FakeClient(failure))

    assert response.status_code == 502
    assert response.json() == {"detail": "The AI assistant is unavailable right now."}


# get_read_only_db


def test_read_only_session_allows_select_and_rejects_writes():
    sessions = get_read_only_db()
    session = next(sessions)
    try:
        assert session.execute(text("SELECT 1")).scalar() == 1
        with pytest.raises((InternalError, ProgrammingError)) as rejected:
            session.execute(text("CREATE TEMP TABLE should_not_exist (id int)"))
        assert "read-only transaction" in str(rejected.value)
    finally:
        session.rollback()
        with pytest.raises(StopIteration):
            next(sessions)
