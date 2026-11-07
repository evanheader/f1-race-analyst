# Design notes

Why the project is built the way it is. Column-by-column details are in [docs/schema.md](docs/schema.md).

## Why these tables

The data has clear relationships (a lap belongs to one race and one driver), so it fits a relational database, with one table per kind of thing.

| Table | Why it exists |
|---|---|
| `races` | The anchor for everything else. It stores the circuit ref because a race name alone can't answer "Who won Monza 2023?" |
| `drivers` | One row per person, keyed on Jolpica's driver ref. Car numbers change between seasons (NOR is #1 in 2026) and three-letter codes get reused, so neither can identify a driver |
| `results` | The official outcome. Lap positions alone can't show who won after retirements and penalties |
| `sprint_results` | Sprints would break the one-row-per-driver-per-race rule on `results`, so they get their own table with the same columns |
| `laps` | The detail behind pace and tire analysis. OpenF1 only goes back to 2023, so older races have results but no laps |
| `pit_stops` | Strategy questions need stops as rows of their own, not as a flag on a lap |

**Two sources, two linking columns.** Jolpica has the official results and OpenF1 has the lap data, and they identify races and drivers differently. `races.openf1_session_key` links a race, and `results.driver_number` links a car in that race to a driver.

**Team is plain text on each result.** Drivers change teams, so it belongs per race. No analysis needs a teams table yet.

**Unique constraints on every table.** They stop a repeated load from doubling the numbers, and upserts use them so a post-race penalty updates the existing row.

**Points are NUMERIC.** The 2021 Belgian GP paid 12.5.

## Cleaning decisions

| Messy data | Decision | Why |
|---|---|---|
| Laps with no time (crashes, red flags) | Keep the row with a null time | The lap happened. Inventing a time would be worse, and averages skip nulls |
| Pit out-laps | Keep them and store OpenF1's flag | They are real laps, but too slow for pace analysis, so the driver average excludes them |
| Deleted laps | Read the car and lap from race control text | No structured field exists. Messages with no lap number are matched by their exact lap time, and laps that are later reinstated are cleared |
| Text numbers from Jolpica | Convert on load | Every Jolpica value is a string |
| Driver identity | Use Jolpica's driver ref, and find a car's driver through that race's results | The car number only means something within one season |
| Drivers who withdrew | Keep the result row, but don't count it in a driver's race total | They never started, even though Jolpica gives them a position |
| Repeated pit rows for one driver and lap | Keep the last one | The unique rule allows one stop per lap. None exist in the data loaded so far |

## Loading

- Races are matched between sources by UTC date, not time, because start times can differ. Night races such as Las Vegas fall a day later in OpenF1, so the loader also tries the next day.
- Each race loads in its own transaction, so a crash never leaves half a race behind.
- Raw responses are cached on disk because Jolpica allows 500 requests per hour. A rerun only fetches what is missing.

## Testing

- **Postgres, not SQLite.** The loader's upserts use Postgres-only `ON CONFLICT`, so tests run against a real `f1_test` database. The tests refuse to start unless the database name ends in `_test`.
- **One rolled-back transaction per test.** The tables are created once per run, and each test's rows disappear when it ends, so tests can run in any order.
- **No network.** HTTP calls are replaced with small hand-written responses shaped like the real APIs, so every case is visible in the test file.
- **The analyst tests use a fake Claude client and a fake clock.** They need no key and cost nothing, and they can check the rate limit, the daily cap and the 60 second limit without waiting.
- **Expected values come from the documented rules**, not from what the code returned. Each rule was checked by breaking the code on purpose and confirming that a test failed. This found the SAI bug below and two tests that were too weak.
- **A bug found this way:** race control sometimes reinstates a lap by number without a time (`CAR 55 (SAI) LAP 1 WILL BE REINSTATED`, Singapore 2024 and Monza 2026), and the loader used to leave that lap deleted.

## AI analyst

`POST /ask` runs a loop: Claude asks for a tool, we run it, and Claude answers from the result. It uses `claude-haiku-5-5`.

| Decision | Why |
|---|---|
| Races are named as people say them: season plus race or circuit name (or round). Drivers by surname, full name or code | The model never sees database ids, so it can't invent one |
| Matching ignores accents, and an exact match wins over a partial one | "Perez" must find Pérez. In 2024 "spa" matched both the Belgian GP and the Spanish GP, so the analyst had to retry with a round number |
| A failed lookup returns a message listing the valid choices | The model can read it and retry, instead of guessing again |
| Tools only run SELECTs, and `/ask` uses a session that Postgres keeps read-only | A tool bug can't change data, because the database refuses the write |
| `get_season_summary` returns season totals from one query | "How many races did Verstappen win in 2023?" needed one lookup per race with the first three tools, which is over the limit of 5 |

**Limits and cost**

- 5 lookups per question. It stops a loop that never ends. Over the limit, the answer says the question was too complex. Every answer also returns `tools_used`, so a reader can see where it came from.
- 5 questions per minute per visitor, $1 per UTC day, and 60 seconds per question. The cap is checked before a question starts, so the last question of the day can finish past $1.
- The per-minute limit is set by `ASK_RATE_LIMIT_PER_MINUTE` (default 5, 0 is off, anything else invalid stops startup). There is no exemption for localhost: behind a reverse proxy every visitor would look like localhost.
- The counters live in the process's memory. They are per process and reset when the server restarts. That is fine for one server.
- Retries are off for the Claude calls, so one call can't outlast the 60 second limit. The cost: a transient API error gives 502 straight away.
- Cost is estimated from documented per-token prices for claude-haiku-5-5. A call that times out is not counted, so the estimate can be low.
- The log records token use and cost for every question, never the question or the answer.
- Phase 5: behind a reverse proxy, the rate limit would see the proxy's address for every visitor. uvicorn would then need `--proxy-headers` and trusted forwarded IPs.

## Eval

`evals/run_eval.py` asks each question in a file through `/ask` and scores the answer.

- Every expected fact must appear in the answer. Case and accents are ignored, and matching is on whole words, so "2" does not match "12" or "2023". A fact can list alternatives, such as "2" or "two".
- A question that should be refused passes when the answer contains a refusal phrase, such as "don't know" or "cannot".
- Each answer was worked out with SQL first, and the query is stored in the question file.
- Known weakness: the grader checks that facts appear, not what they are said about. "Verstappen was slower than Norris" would pass a question that expects "Norris". Comparison answers were read by hand to cover this. It can also reject a correct answer worded differently, as it did with "twice".
- It runs by hand and never in CI, because it calls Claude and costs money.

## Known limits

- OpenF1's free tier returns 401 while any F1 session is live, so loads must run outside sessions. The API is unaffected because it reads from our own database.
- `laps.position` is derived from a time series of position changes. It matched Jolpica's official lap positions on 99.8% of laps at Monza 2023 and 98.8% at Zandvoort 2024. A driver's final lap is less reliable, so use `results` for finishing order.
- Pit stops are missing before the 2023 Spanish GP, and stationary times before the 2024 US GP, because OpenF1 doesn't have them.
- Results go back to 2000 and lap data to 2023, so career stats for drivers who started before 2000 are partial, and average lap time only covers 2023 onward.
- The analyst answers one question at a time with no memory, and allows 5 lookups, so broad questions are turned away as too complex.
- It only knows what the tools return: results from 2000, and lap, tire and pit data from 2023. Its refusals for older data rely on the model following its instructions.
- The rate limit and daily spend cap are in memory. They reset on restart and would not be shared between several servers.
