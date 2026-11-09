"""Tests for POST /ask. No network and no API key: Claude is replaced by a scripted fake."""

import datetime
import json
import logging
from types import SimpleNamespace

import anthropic
import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import InternalError, ProgrammingError

from app import analyst, limits, main
from app.database import get_read_only_db
from app.main import app, get_anthropic_client
from app.tools import TOOLS


class FakeClient:
    """Stands in for anthropic.Anthropic: returns scripted responses, records every call."""

    def __init__(self, *responses, after_call=None):
        self.responses = list(responses)
        self.calls = []
        self.messages = self
        self.after_call = after_call  # runs after each call, e.g. to move the fake clock
        self._options = {}

    def with_options(self, **options):
        self._options = options
        return self

    def create(self, **kwargs):
        kwargs["messages"] = list(kwargs["messages"])  # the loop keeps appending to its list
        kwargs.update(self._options)  # so the per-request timeout shows up in the call record
        self._options = {}
        self.calls.append(kwargs)
        if self.after_call:
            self.after_call()
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def usage(input_tokens, output_tokens):
    return SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)


def text_reply(words, input_tokens=100, output_tokens=20):
    return SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=words)],
        usage=usage(input_tokens, output_tokens),
    )


def cut_off_reply(*blocks):
    return SimpleNamespace(stop_reason="max_tokens", content=list(blocks), usage=usage(100, 4096))


def tool_block(id, name, **tool_input):
    return SimpleNamespace(type="tool_use", id=id, name=name, input=tool_input)


def tool_reply(*blocks, input_tokens=100, output_tokens=20):
    return SimpleNamespace(
        stop_reason="tool_use", content=list(blocks), usage=usage(input_tokens, output_tokens)
    )


def monza_call(id, **tokens):
    return tool_reply(tool_block(id, "get_race_results", season=2023, race="monza"), **tokens)


class Clock:
    """A fake clock for the limits: .seconds is the monotonic time, .date the UTC date."""

    def __init__(self):
        self.seconds = 1000.0
        self.date = datetime.date(2026, 11, 7)


@pytest.fixture
def clock(monkeypatch):
    fake = Clock()
    monkeypatch.setattr(limits, "monotonic", lambda: fake.seconds)
    monkeypatch.setattr(limits, "utc_today", lambda: fake.date)
    return fake


@pytest.fixture(autouse=True)
def fresh_limits(monkeypatch):
    """The limiter and the cost total are process-wide: start and leave every test clean."""
    monkeypatch.setattr(limits, "RATE_LIMIT", 5)  # whatever the local .env says
    limits.reset()
    yield
    limits.reset()


@pytest.fixture
def ask(client, db):
    """Post a question with the given fake Claude. Returns (response, fake)."""
    app.dependency_overrides[get_read_only_db] = lambda: db

    def run(fake, question="Who won Monza 2023?", **extra):
        app.dependency_overrides[get_anthropic_client] = lambda: fake
        return client.post("/ask", json={"question": question, **extra}), fake

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
    assert call["system"].startswith(analyst.SYSTEM_PROMPT)
    assert "never from memory" in call["system"]
    assert "more than one driver, team or race" in call["system"]
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
    # 8 calls are allowed. The 9th is not run and nothing more is sent to Claude.
    response, fake = ask(FakeClient(*[monza_call(f"t{n}") for n in range(9)]))

    body = response.json()
    assert response.status_code == 200
    assert body["answer"] == analyst.TOO_COMPLEX_ANSWER
    assert "too complex" in body["answer"]
    assert len(body["tools_used"]) == 8
    assert len(fake.calls) == 9


def test_a_reply_cut_off_with_no_text_gives_the_fixed_answer(ask, monza):
    # The observed bug: tool calls, then a response that hit max_tokens with no text block.
    response, _ = ask(FakeClient(monza_call("t1"), cut_off_reply()))

    assert response.json()["answer"] == analyst.CUT_OFF_ANSWER
    assert len(response.json()["tools_used"]) == 1


def test_an_empty_or_blank_final_reply_never_gives_a_blank_answer(ask):
    for reply in (text_reply(""), text_reply("  \n")):
        response, _ = ask(FakeClient(reply))

        assert response.json()["answer"] == analyst.CUT_OFF_ANSWER


def test_a_reply_cut_off_in_the_middle_of_a_sentence_says_so(ask):
    cut = cut_off_reply(SimpleNamespace(type="text", text="Copy. Verstappen won, then"))
    response, _ = ask(FakeClient(cut))

    assert response.json()["answer"] == "Copy. Verstappen won, then (The answer was cut off.)"


def test_a_batch_that_would_cross_the_limit_is_not_run(ask, monza):
    pair = tool_reply(
        tool_block("x", "get_race_results", season=2023, race="monza"),
        tool_block("y", "get_race_results", season=2023, race="monza"),
    )
    response, _ = ask(FakeClient(*[monza_call(f"t{n}") for n in range(7)], pair))

    assert response.json()["answer"] == analyst.TOO_COMPLEX_ANSWER
    assert len(response.json()["tools_used"]) == 7


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


# Conversation history


def turn(question, answer):
    return {"question": question, "answer": answer}


def test_history_is_sent_as_plain_turns_before_the_new_question(ask):
    history = [turn("How many wins?", "Which season?"), turn("2023", "Max Verstappen won 19.")]
    response, fake = ask(FakeClient(text_reply("ok")), question="And Perez?", history=history)

    assert response.status_code == 200
    assert fake.calls[0]["messages"] == [
        {"role": "user", "content": "How many wins?"},
        {"role": "assistant", "content": "Which season?"},
        {"role": "user", "content": "2023"},
        {"role": "assistant", "content": "Max Verstappen won 19."},
        {"role": "user", "content": "And Perez?"},
    ]


def test_history_turns_are_stripped(ask):
    _, fake = ask(FakeClient(text_reply("ok")), history=[turn("  Who won?  ", "  Verstappen.\n")])

    assert fake.calls[0]["messages"][:2] == [
        {"role": "user", "content": "Who won?"},
        {"role": "assistant", "content": "Verstappen."},
    ]


def test_no_history_still_works(ask):
    for extra in ({}, {"history": []}):
        response, fake = ask(FakeClient(text_reply("ok")), **extra)

        assert response.status_code == 200
        assert len(fake.calls[0]["messages"]) == 1


def test_history_response_shape_is_unchanged(ask):
    response, _ = ask(FakeClient(text_reply("Copy.")), history=[turn("Hi", "Hello.")])

    assert response.json() == {"answer": "Copy.", "tools_used": []}


def test_three_history_turns_are_accepted_and_four_give_422(ask):
    assert ask(FakeClient(text_reply("ok")), history=[turn("q", "a")] * 3)[0].status_code == 200

    response, fake = ask(FakeClient(), history=[turn("q", "a")] * 4)

    assert response.status_code == 422
    assert fake.calls == []


@pytest.mark.parametrize(
    "bad",
    [turn("q", "x" * 4001), turn("x" * 501, "a"), turn("", "a"), turn("q", "   ")],
    ids=["long-answer", "long-question", "empty-question", "blank-answer"],
)
def test_a_bad_history_turn_gives_422(ask, bad):
    response, fake = ask(FakeClient(), history=[bad])

    assert response.status_code == 422
    assert fake.calls == []


def test_a_4000_character_history_answer_is_accepted(ask):
    response, _ = ask(FakeClient(text_reply("ok")), history=[turn("q", "x" * 4000)])

    assert response.status_code == 200


def test_the_system_prompt_asks_for_a_missing_season_and_uses_earlier_turns():
    assert "ask which season" in analyst.SYSTEM_PROMPT
    assert "Earlier turns in the conversation are context" in analyst.SYSTEM_PROMPT
    assert "answer the latest question" in analyst.SYSTEM_PROMPT
    assert "it is the answer" in analyst.SYSTEM_PROMPT
    assert "never the reply on its own" in analyst.SYSTEM_PROMPT


def test_the_system_prompt_names_this_year_and_only_counts_drivers_who_raced(ask, monza, clock):
    _, fake = ask(FakeClient(text_reply("ok")))

    system = fake.calls[0]["system"]
    assert "Today is 2026-11-07." in system
    assert "latest season in the data is 2023" in system
    assert "2022 is 'last year'" in system
    assert "did not race then" in system
    assert "never ask the user to confirm a name or race" in system


def test_the_system_prompt_has_no_dates_when_no_races_are_loaded(db):
    assert analyst.system_prompt(db) == analyst.SYSTEM_PROMPT


# Safety limits


def test_the_sixth_question_in_a_minute_gets_429_and_the_first_five_do_not(ask, clock, caplog):
    fake = FakeClient(*[text_reply("ok") for _ in range(5)])
    for _ in range(5):
        response, _ = ask(fake)
        assert response.status_code == 200

    with caplog.at_level(logging.WARNING, logger="app.ask"):
        response, _ = ask(fake)

    assert response.status_code == 429
    assert response.json() == {"detail": "Too many questions. Try again in a minute."}
    assert len(fake.calls) == 5  # refused before any Claude call
    assert [r.levelname for r in caplog.records if r.levelno >= logging.WARNING] == ["WARNING"]
    assert "rate limit" in caplog.text


def test_another_ip_is_not_affected_by_the_rate_limit(ask, clock):
    fake = FakeClient(*[text_reply("ok") for _ in range(6)])
    for _ in range(5):
        ask(fake)
    assert ask(fake)[0].status_code == 429

    other = TestClient(app, client=("203.0.113.9", 50000))
    assert other.post("/ask", json={"question": "Who won?"}).status_code == 200


def test_the_rate_limit_window_slides(ask, clock):
    fake = FakeClient(*[text_reply("ok") for _ in range(6)])
    for _ in range(5):
        ask(fake)
        clock.seconds += 10  # the 5 questions are at t = 0, 10, 20, 30, 40
    assert ask(fake)[0].status_code == 429  # t = 50

    clock.seconds = 1000.0 + 60  # the first question is now a minute old, the others are not
    assert ask(fake)[0].status_code == 200
    assert ask(fake)[0].status_code == 429


def test_the_rate_limit_defaults_to_5(monkeypatch):
    monkeypatch.delenv("ASK_RATE_LIMIT_PER_MINUTE", raising=False)

    assert limits.read_rate_limit() == 5


def test_the_rate_limit_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("ASK_RATE_LIMIT_PER_MINUTE", "12")

    assert limits.read_rate_limit() == 12


@pytest.mark.parametrize("value", ["-1", "abc", "2.5", ""])
def test_an_invalid_rate_limit_setting_fails_loudly(monkeypatch, value):
    monkeypatch.setenv("ASK_RATE_LIMIT_PER_MINUTE", value)

    with pytest.raises(ValueError, match="ASK_RATE_LIMIT_PER_MINUTE"):
        limits.read_rate_limit()


def test_a_rate_limit_of_0_allows_unlimited_questions(ask, clock, monkeypatch):
    monkeypatch.setattr(limits, "RATE_LIMIT", 0)
    fake = FakeClient(*[text_reply("ok") for _ in range(20)])

    assert all(ask(fake)[0].status_code == 200 for _ in range(20))
    assert not limits._recent_requests  # nothing was recorded


def test_cost_is_estimated_from_usage_at_haiku_prices(ask, monza, clock):
    # $0.10 per million input tokens and $0.50 per million output tokens.
    # Call 1: 10,000 in = $0.001 and 2,000 out = $0.001. Call 2: 4,000 in = $0.0004 and
    # 1,000 out = $0.0005. Together $0.002 + $0.0009 = $0.0029.
    fake = FakeClient(
        monza_call("t1", input_tokens=10_000, output_tokens=2_000),
        text_reply("Max Verstappen won.", input_tokens=4_000, output_tokens=1_000),
    )
    ask(fake)

    assert limits.spent_today() == pytest.approx(0.0029)


def test_at_or_over_the_daily_cap_gives_503_and_no_claude_call(ask, clock, caplog):
    limits.add_cost(1.00)
    fake = FakeClient(text_reply("ok"))

    with caplog.at_level(logging.WARNING, logger="app.ask"):
        response, _ = ask(fake)

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The AI assistant has reached its daily limit. Try again tomorrow."
    }
    assert fake.calls == []
    assert "daily cost cap" in caplog.text


def test_a_question_that_starts_under_the_cap_may_finish_over_it(ask, clock):
    limits.add_cost(0.99)
    # 20,000,000 input tokens would be $2, so this one call takes the total well past $1.
    response, _ = ask(FakeClient(text_reply("ok", input_tokens=20_000_000)))

    assert response.status_code == 200
    assert limits.spent_today() > 1.00
    assert ask(FakeClient(text_reply("ok")))[0].status_code == 503


def test_the_daily_total_starts_again_on_a_new_utc_date(ask, clock):
    limits.add_cost(1.00)
    assert ask(FakeClient(text_reply("ok")))[0].status_code == 503

    clock.date += datetime.timedelta(days=1)
    response, _ = ask(FakeClient(text_reply("ok")))

    assert response.status_code == 200
    assert limits.spent_today() == pytest.approx(0.00001 + 0.00001)  # 100 in, 20 out


def test_each_call_gets_the_time_left_as_its_timeout(ask, monza, clock):
    # Every call takes 25 s of the 60 s: the calls start with 60, 35 and 10 s left, and a
    # fourth would start with none.
    def slow():
        clock.seconds += 25

    fake = FakeClient(*[monza_call(f"t{n}") for n in range(3)], after_call=slow)
    response, _ = ask(fake)

    assert [call["timeout"] for call in fake.calls] == [60.0, 35.0, 10.0]
    assert response.status_code == 504
    assert response.json() == {"detail": "The AI assistant took too long to answer."}


def test_passing_60_seconds_mid_loop_gives_504_and_no_further_call(ask, monza, clock):
    def passes_the_deadline():
        clock.seconds += 61

    fake = FakeClient(monza_call("t1"), text_reply("never asked"), after_call=passes_the_deadline)
    response, _ = ask(fake)

    assert response.status_code == 504
    assert len(fake.calls) == 1


def test_one_info_log_line_per_question_with_counts_and_no_text(ask, monza, clock, caplog):
    # 300 + 200 = 500 input tokens and 50 + 30 = 80 output tokens: $0.00005 + $0.00004.
    fake = FakeClient(
        monza_call("t1", input_tokens=300, output_tokens=50),
        text_reply("Max Verstappen won.", input_tokens=200, output_tokens=30),
    )
    with caplog.at_level(logging.INFO, logger="app.ask"):
        ask(fake, question="Who won Monza 2023?")

    [record] = [r for r in caplog.records if r.name == "app.ask"]
    assert record.name == "app.ask"
    assert record.levelname == "INFO"
    assert record.getMessage() == (
        "ask tool_calls=1 stop_reason=end_turn input_tokens=500 output_tokens=80 "
        "cost=$0.000090 "
        "total_today=$0.000090 duration=0.0s"
    )
    assert "Monza" not in caplog.text
    assert "Verstappen" not in caplog.text


def test_the_log_line_says_how_the_last_reply_ended(ask, caplog):
    with caplog.at_level(logging.INFO, logger="app.ask"):
        ask(FakeClient(cut_off_reply()))

    assert "stop_reason=max_tokens" in caplog.text


def test_the_log_line_is_written_even_when_the_question_fails(ask, monza, clock, caplog):
    def slow():
        clock.seconds += 61

    with caplog.at_level(logging.INFO, logger="app.ask"):
        ask(FakeClient(monza_call("t1"), after_call=slow))

    assert "ask tool_calls=1 " in caplog.text
    assert "duration=61.0s" in caplog.text


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
