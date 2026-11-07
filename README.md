# f1-race-analyst

[![CI](https://github.com/evanheader/f1-race-analyst/actions/workflows/ci.yml/badge.svg)](https://github.com/evanheader/f1-race-analyst/actions/workflows/ci.yml)

A REST API for looking up Formula 1 race results, lap times, tire stints and pit stops, built with FastAPI and PostgreSQL. An AI analyst answers questions in plain English from the same database, using Claude and tool calling.

This is an unofficial fan project, not affiliated with Formula 1. Race data comes from [Jolpica](https://github.com/jolpica/jolpica-f1) and [OpenF1](https://openf1.org/).

## How to run

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) running.

1. Copy `.env.example` to a new file named `.env`. The values work as they are for running on your own computer.

   ```bash
   cp .env.example .env
   ```

2. Start the database and the API.

   ```bash
   docker compose up --build -d
   ```

3. Create the tables. You only need to do this once.

   ```bash
   docker compose exec api python -m scripts.create_tables
   ```

4. Load the 2023 and 2024 seasons. This takes about 10 minutes. It is safe to run again: rows are updated, not duplicated.

   ```bash
   docker compose exec api python -m scripts.load_data
   ```

   If it stops with a `401` or `429`, a live F1 session or a rate limit is blocking the data source. Run the same command again later.

5. Open <http://localhost:8000/docs> to try the API, or <http://localhost:8000/races> to see the races.

To stop everything, run `docker compose down`. Your data is kept for next time.

### Optional: ask the AI analyst

Everything above works without this. Only `POST /ask` needs a key.

1. Put your key from [console.anthropic.com](https://console.anthropic.com) in `.env` as `ANTHROPIC_API_KEY`, then run `docker compose up -d` again so the API picks it up.

   Every question costs a little money. Set a spending limit in the Anthropic console, and never commit your key.

2. Ask a question, either on the `/docs` page (`POST /ask`) or with curl.

   ```bash
   curl -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "Who won Monza 2023?"}'
   ```

   You get the answer and the tools Claude called to find it:

   ```json
   {
     "answer": "Max Verstappen won the 2023 Italian Grand Prix at Monza.",
     "tools_used": [{"name": "get_race_results", "input": {"season": 2023, "race": "monza"}}]
   }
   ```

   Without a key, `/ask` returns 503. The rest of the API is not affected.

## AI analyst

`POST /ask` sends your question to Claude (`claude-haiku-5-5`). Claude looks things up with four tools, then answers from what they return. The tools only read from the database.

| Tool | What it does |
|---|---|
| `get_race_results` | The finishing order of one race, with grid, team, status and points |
| `compare_drivers` | Two drivers in one race: result, average and fastest clean lap, pit stops |
| `get_pit_strategy` | One driver's tire stints and pit stops in a race |
| `get_season_summary` | One driver's or team's season totals: wins, podiums, points, retirements |

Limits on `/ask`:

- 5 questions per minute per visitor (429 after that).
- $1 per UTC day of estimated spend, then 503 until the next day.
- 60 seconds per question (504 if it takes longer).
- 5 lookups per question.
- F1 data questions only. Anything else should be refused.

## Accuracy eval

`evals/` holds 25 questions with answers worked out in SQL against the database (the query is stored beside each question). 4 of them are questions the analyst should refuse. A hidden set of 5 more questions was written separately and scored once, at the end.

To run it, start the API with a key, then run `uv run python evals/run_eval.py`. It prints every answer and the tools used, then the score. It costs a little, so run it by hand. It never runs in CI.

All runs used claude-haiku-5-5 on 2026-11-07.

| Run | What changed | Score (run 1 / run 2) |
|---|---|---|
| 1 | Baseline: three tools | 23/25 / 23/25 |
| 2 | Added a season summary tool (season-count questions needed more than 5 lookups) | 24/25 / 25/25 |
| 3 | Exact race names win over partial matches ("spa" also matched the Spanish GP); grader also accepts "twice" | 25/25 / 25/25 |
| Hidden | Scored once, after tuning | 5/5 |

What the numbers do and do not show:

- Run 2's only miss was a correct answer the grader rejected ("twice"). Part of run 3's gain is a grader fix, not a better analyst.
- The grader checks that facts appear, not who is named as ahead. Comparison answers were also read by hand, and all were correct.
- 100% on the practice set suggests the questions are on the easy side. That is why the hidden score matters.
- Hidden set: no misses. One answer was clumsy: for Piastri's Hungarian GP strategy it wrote "a one-stop... actually a two-stop strategy" before listing the right stints. The grader passed it.

## Run the tests

The tests use a separate `f1_test` database, so they never touch your real data, and they never call the internet. The AI analyst tests use a fake Claude client, so they need no key and cost nothing.

1. Start the database, and create `f1_test` once.

   ```bash
   docker compose up -d db
   docker compose exec db createdb -U f1 f1_test
   ```

2. Run the checks that CI runs.

   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest --cov=app --cov=scripts
   ```

## More documentation

- [DESIGN.md](DESIGN.md): why the project is built this way
- [docs/schema.md](docs/schema.md): every table and column
- [docs/api-reference.md](docs/api-reference.md): notes on the two data sources
