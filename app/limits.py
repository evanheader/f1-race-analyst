"""Safety limits for POST /ask: a per-IP rate limit and a daily cost cap.

All state lives in this process's memory, so the counters are per process and reset when the
server restarts. That is fine for a single server; running several would need shared storage.
"""

import datetime
import os
import threading
import time
from collections import defaultdict, deque

from dotenv import load_dotenv


def read_rate_limit() -> int:
    """Questions per minute per IP from ASK_RATE_LIMIT_PER_MINUTE (default 5). 0 turns it off."""
    raw = os.environ.get("ASK_RATE_LIMIT_PER_MINUTE", "5")
    try:
        value = int(raw)
    except ValueError:
        value = -1
    if value < 0:
        raise ValueError(
            f"ASK_RATE_LIMIT_PER_MINUTE must be a whole number, 0 or more. Got {raw!r}."
        )
    return value


load_dotenv()
RATE_LIMIT = read_rate_limit()  # questions per client IP ... (0 means no limit)
RATE_WINDOW_SECONDS = 60.0  # ... per sliding window
DAILY_COST_CAP = 1.00  # dollars per UTC day
QUESTION_TIME_LIMIT_SECONDS = 60.0  # for all Claude calls in one question

# claude-haiku-5-5, dollars per million tokens, from the claude-api skill (checked 2026-11-07).
# That price holds for prompts up to 100K tokens; ours are far smaller. Cache reads and writes
# are priced differently, but the analyst does not use prompt caching, so they are ignored.
INPUT_DOLLARS_PER_MILLION_TOKENS = 0.10
OUTPUT_DOLLARS_PER_MILLION_TOKENS = 0.50

# Tests replace these two to control time.
monotonic = time.monotonic


def utc_today() -> datetime.date:
    return datetime.datetime.now(datetime.UTC).date()


_lock = threading.Lock()
_recent_requests: dict[str, deque[float]] = defaultdict(deque)
_spend = {"date": None, "dollars": 0.0}


def reset() -> None:
    with _lock:
        _recent_requests.clear()
        _spend.update(date=None, dollars=0.0)


def allow_request(ip: str) -> bool:
    """Record a question from this IP and say whether it is within the rate limit."""
    if RATE_LIMIT == 0:
        return True
    now = monotonic()
    with _lock:
        recent = _recent_requests[ip]
        while recent and recent[0] <= now - RATE_WINDOW_SECONDS:
            recent.popleft()
        if len(recent) >= RATE_LIMIT:
            return False
        recent.append(now)
        return True


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * INPUT_DOLLARS_PER_MILLION_TOKENS
        + output_tokens * OUTPUT_DOLLARS_PER_MILLION_TOKENS
    ) / 1_000_000


def spent_today() -> float:
    with _lock:
        return _today_spend()


def add_cost(dollars: float) -> None:
    with _lock:
        _today_spend()
        _spend["dollars"] += dollars


def _today_spend() -> float:
    """Today's total, starting a new one when the UTC date has changed. Hold the lock."""
    today = utc_today()
    if _spend["date"] != today:
        _spend.update(date=today, dollars=0.0)
    return _spend["dollars"]
