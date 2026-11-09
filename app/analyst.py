"""The AI analyst: asks Claude a question and lets it look things up through the tools."""

import json
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import limits
from app.models import Race
from app.tools import TOOLS, run_tool

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 4096
MAX_TOOL_CALLS = 8

SYSTEM_PROMPT = (
    "You are an F1 race engineer on the pit wall, reporting to the user over the team radio. "
    "Answer only from the results of the tools, never from memory. If the tools cannot answer "
    "the question, or it is not about F1 race data, say you don't know or can't help. If a "
    "name in the question could mean more than one driver, team or race (for example two "
    "drivers with the same surname, or two races in the same country in one season), answer "
    "for each match and say that there are several, rather than picking one or asking which. "
    "Check for other matches before answering, even when the first one looks right. If the "
    "question needs a season and gives none, and the earlier turns don't give one, ask which "
    "season in one short sentence instead of guessing or looking things up. 'This year', "
    "'this season' and 'the current season' are not missing: they mean the latest season in "
    "the data, given at the end of this prompt, so look them up. Only drivers who raced in the "
    "season or race asked about are matches: a first name or surname shared with someone who "
    "did not race then (a retired driver, say) is not a second match, so check the season's "
    "entrants with the tools before saying a name is unclear, and never ask the user to "
    "confirm a name or race. Earlier turns in "
    "the conversation are context. If your last message asked the user a question and the "
    "latest message is a short reply to it (a season, a driver, a race), it is the answer: "
    "combine it with the question they asked before and answer that question, never the "
    "reply on its own. Otherwise answer the latest question. Be economical with lookups: "
    "get_race_results is not needed to find a race, and one get_pit_strategy call per driver "
    "per race is enough. Talk like a race engineer: "
    "calm, short and direct, with the key fact first. You may open with a radio word such as "
    "'Copy.' and use F1 shorthand such as P3 for third place, but no slang, jokes or "
    "catchphrases. State the key fact plainly: use the driver's full name and give numbers "
    "with their units. Write whole numbers without a decimal point (8 points, not 8.0)."
)

TOO_COMPLEX_ANSWER = (
    "This question was too complex to answer within the lookup limit. "
    "Try asking about one race or one driver at a time."
)

CUT_OFF_ANSWER = (
    "The answer was cut off before it finished. Try asking about one race or one driver at a time."
)


def system_prompt(db: Session) -> str:
    """The standing instructions plus today's date and the latest season the data holds."""
    latest = db.scalar(select(func.max(Race.season)))
    if latest is None:
        return SYSTEM_PROMPT
    return (
        f"{SYSTEM_PROMPT} Today is {limits.utc_today().isoformat()}. The latest season in the "
        f"data is {latest}: that is 'this year' and 'this season', and {latest - 1} is "
        "'last year' and 'last season'. Say which season you used."
    )


class QuestionTimeout(Exception):
    """The question used up its overall time limit."""


@dataclass
class Run:
    """What one question has used so far. The caller logs it, even when the question fails."""

    deadline: float  # on the limits.monotonic() clock
    tool_calls: int = 0
    stop_reason: str | None = None  # of the last response
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


def answer_question(client, db: Session, question: str, run: Run, history=()) -> dict:
    """Run the tool-use loop and return the answer with the tools that were called.

    history is the earlier turns (each with .question and .answer), sent as plain text.
    """
    messages = []
    for turn in history:
        messages.append({"role": "user", "content": turn.question})
        messages.append({"role": "assistant", "content": turn.answer})
    messages.append({"role": "user", "content": question})
    tools_used = []
    system = system_prompt(db)
    while True:
        remaining = run.deadline - limits.monotonic()
        if remaining <= 0:
            raise QuestionTimeout
        # The timeout is per attempt, so retries are off: one call can't outlast the deadline.
        response = client.with_options(timeout=remaining, max_retries=0).messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        run.input_tokens += response.usage.input_tokens
        run.output_tokens += response.usage.output_tokens
        run.stop_reason = response.stop_reason
        cost = limits.estimate_cost(response.usage.input_tokens, response.usage.output_tokens)
        run.cost += cost
        # A question that starts under the daily cap may finish even if this pushes past it.
        limits.add_cost(cost)
        if response.stop_reason != "tool_use":
            answer = "".join(block.text for block in response.content if block.type == "text")
            if not answer.strip():
                answer = CUT_OFF_ANSWER
            elif response.stop_reason == "max_tokens":
                answer += " (The answer was cut off.)"
            return {"answer": answer, "tools_used": tools_used}

        calls = [block for block in response.content if block.type == "tool_use"]
        if len(tools_used) + len(calls) > MAX_TOOL_CALLS:
            return {"answer": TOO_COMPLEX_ANSWER, "tools_used": tools_used}

        results = []
        for call in calls:
            output = run_tool(db, call.name, call.input)
            tools_used.append({"name": call.name, "input": call.input})
            run.tool_calls += 1
            result = {
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": json.dumps(output),
            }
            if "error" in output:
                result["is_error"] = True
            results.append(result)
        # The assistant turn goes back unchanged (thinking blocks included).
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": results})
