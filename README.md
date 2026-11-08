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

4. Load some data. Pick one:

   **Quick demo (a few seconds, no internet needed).** Loads one race, the 2025 British Grand Prix: results, every lap with its tire, and every pit stop. It was a mixed-conditions race that Norris won and Hülkenberg took third in from 19th on the grid.

   ```bash
   docker compose exec api python -m scripts.load_sample
   ```

   **Full 2025 season.** This downloads from the data sources and takes several minutes. It is safe to run again: rows are updated, not duplicated.

   ```bash
   docker compose exec api python -m scripts.load_data
   ```

   If it stops with a `401` or `429`, a live F1 session or a rate limit is blocking the data source. Run the same command again later. To load other seasons, pass them: `python -m scripts.load_data 2023 2024`.

5. Open <http://localhost:8000/docs> to try the API, or <http://localhost:8000/races> to see the races. With the quick demo, try <http://localhost:8000/races/1/results> and <http://localhost:8000/races/1/pit-stops>.

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

   The 5 questions per minute limit gets in the way of eval runs. For local development only, set `ASK_RATE_LIMIT_PER_MINUTE=0` in `.env` and run `docker compose up -d` again to switch it off.

## AI analyst

`POST /ask` sends your question to Claude (`claude-haiku-5-5`). Claude looks things up with five tools, then answers from what they return. The tools only read from the database.

| Tool | What it does |
|---|---|
| `get_race_results` | The finishing order of one race, with grid, team, status and points |
| `compare_drivers` | Two drivers in one race: result, average and fastest clean lap, pit stops |
| `get_pit_strategy` | One driver's tire stints and pit stops in a race |
| `get_season_summary` | One driver's or team's season totals: wins, podiums, points, retirements |
| `get_laps` | A driver's laps with their fastest clean lap and deleted laps, or the running order at the end of a lap |

If a name could mean more than one driver, team or race (two Schumachers, two races in Spain), the analyst answers for every match.

Limits on `/ask`:

- 5 questions per minute per visitor (429 after that). `ASK_RATE_LIMIT_PER_MINUTE=0` switches it off for local development; never on a public server.
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

### Hard set

The first set scored 25/25, which is too easy to tell a good change from a bad one. `evals/hard.jsonl` has 30 harder questions in 7 categories, plus 6 hidden ones. Each question has a `why_hard` note.

| Category | What it tests | Example |
|---|---|---|
| `trap` | Data that differs from common memory, and false premises | "Why was Hamilton disqualified from the 2024 Belgian Grand Prix?" (Russell was) |
| `ambiguous` | A name that fits more than one driver or race | "Who won at Silverstone in 2020?" (two races, two winners) |
| `multi_hop` | One lookup feeds the next | "What tire did the winner of the 2023 Italian Grand Prix start on?" |
| `aggregation` | Arithmetic over results | "Which team scored the most points at the 2023 Belgian Grand Prix, and how many?" |
| `alias` | Nicknames and team names that differ from the database | "How many podiums did Kimi have in 2025?" |
| `capability` | Facts in the database that the tools did not return at first | "Who was leading the 2024 São Paulo Grand Prix at the end of lap 35?" |
| `boundary` | Questions the analyst should decline | "Who won the 2026 Mexico City Grand Prix?" (no results loaded yet) |

The grader gained two things. A question can list `forbidden` facts that must not appear in the answer. The run prints a score for each category as well as the total.

To run it, start the API with a key, then run `uv run python evals/run_eval.py evals/hard.jsonl`. Set `ASK_RATE_LIMIT_PER_MINUTE=0` in `.env` to avoid waiting on the rate limit locally. Without that, the runner waits 61 seconds and asks again.

All runs used claude-haiku-5-5 on 2026-11-07.

| Run | What changed | Hard set (run 1 / run 2) | Original set |
|---|---|---|---|
| 1 | Baseline (four tools) | 24/30 / 25/30 | 25/25 |
| 2 | Added `get_laps` | 28/30 / 28/30 | 25/25 |
| 3 | Answer every reading of an ambiguous name; race results list the season's races. Grader: more refusal wording, per-category scores | 30/30 / 30/30 | 25/25 |
| 4 | An exact driver code or name wins over a partial name ("VER" also matched Oliver Bearman) | 29/30 (one run) | 25/25 |
| Hidden | 6 questions written alongside the set and kept from tuning, scored once at the end | 6/6 | |

What the numbers do and do not show:

- The baseline showed two real weaknesses: missing lap data (0/4) and ambiguous names (1-2/3). Traps, arithmetic and nicknames were already strong.
- Part of run 3's gain is a grader fix. A correct refusal ("doesn't include") had failed because the phrase was not in the list.
- Run 4's one miss is hard09 (two 2026 races in Spain). It passed in both run-3 runs and missed once in run 4, so it is run-to-run variance. It was left alone rather than tuned to that question.
- The hidden hard set was written by the same agent that wrote the hard set, not by the developer as with the first hidden set. It guards against tuning, but it is not fully independent.

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
