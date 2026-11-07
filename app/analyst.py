"""The AI analyst: asks Claude a question and lets it look things up through the tools."""

import json

from sqlalchemy.orm import Session

from app.tools import TOOLS, run_tool

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 4096
MAX_TOOL_CALLS = 5

SYSTEM_PROMPT = (
    "You are an F1 race analyst. Answer only from the results of the tools, never from "
    "memory. If the tools cannot answer the question, or it is not about F1 race data, say "
    "you don't know or can't help. Keep answers short and state the key fact plainly: use "
    "the driver's full name and give numbers with their units."
)

TOO_COMPLEX_ANSWER = (
    "This question was too complex to answer within the lookup limit. "
    "Try asking about one race or one driver at a time."
)


def answer_question(client, db: Session, question: str) -> dict:
    """Run the tool-use loop and return the answer with the tools that were called."""
    messages = [{"role": "user", "content": question}]
    tools_used = []
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        if response.stop_reason != "tool_use":
            answer = "".join(block.text for block in response.content if block.type == "text")
            return {"answer": answer, "tools_used": tools_used}

        calls = [block for block in response.content if block.type == "tool_use"]
        if len(tools_used) + len(calls) > MAX_TOOL_CALLS:
            return {"answer": TOO_COMPLEX_ANSWER, "tools_used": tools_used}

        results = []
        for call in calls:
            output = run_tool(db, call.name, call.input)
            tools_used.append({"name": call.name, "input": call.input})
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
