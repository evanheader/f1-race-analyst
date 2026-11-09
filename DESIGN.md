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
| `get_laps` returns a driver's laps, the running order at the end of a lap, or one driver's single lap | The laps table already held per-lap position, times and deleted flags, but no tool returned them, so the analyst refused "Who was leading on lap 35?". Positions are derived, and least reliable around pit stops and on a final lap, so the tool says to use `get_race_results` for final positions |
| If a name could mean several drivers, teams or races, the analyst answers for each. Race results also list the season's races (`season_races`) | Asked about "Schumacher" at San Marino 2001, it picked Michael and treated Ralf's win as an aside. Asked about "the Grand Prix in Spain" in 2026, it found the Spanish GP and never learned of the Barcelona GP |
| An exact driver code, driver ref or full name wins over a partial name, as it already did for races | At the 2024 São Paulo GP "VER" matched Max Verstappen by code and Oliver Bearman by name ("Oliver"), so the lookup failed as ambiguous |
| It talks like a race engineer on team radio: calm, short, key fact first, P-numbers for positions, no slang | It suits the site. Facts stay plain because the eval checks for them. The first version cost hard-set points: answers said "8.0 points" (the grader wants "8"), and "short" won over "answer every match". The prompt now asks for whole numbers, and puts the every-match rule before the tone |
| `get_championship_progression` returns a driver's position, points and gap to the leader after every round | "When did the gap to the leader drop below 10?" needs the standings after each round, and season totals could not give them. Ties are ranked by wins so far, which is simpler than the official count-back |
| `/ask` takes up to 3 earlier questions and answers as `history`, sent as plain text without their tool calls | The engineer can ask "Which season?" and use the reply. The API stays stateless: the browser holds the conversation, and 3 turns keeps the cost per question small |
| An empty or cut-off reply returns a fixed answer, and the log records `stop_reason` | A question once made 4 lookups and then hit the 4,096 token limit with no text, and the site showed a blank answer |

**Limits and cost**

- 8 lookups per question, up from 5 so that two drivers across two races fit. It stops a loop that never ends. Over the limit, the answer says the question was too complex. Every answer also returns `tools_used`, so a reader can see where it came from.
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
- **Hard set.** `evals/hard.jsonl` has 31 questions in 7 categories (trap, ambiguous, multi_hop, aggregation, alias, capability, boundary), added because the first set scored 25/25 and could no longer separate a good change from a bad one. 6 more questions are kept hidden and scored once at the end.
- **Forbidden facts.** A question can list `forbidden` facts, and the answer fails if any appears. Use it only where a correct answer would never contain them, such as phrases from the system prompt in a prompt-injection test. "Max" in a question about Jos Verstappen was tried and dropped, because a correct answer can say "Jos, Max's father".
- **Per-category scores.** The runner prints a score for each category after the total, so a change that helps one kind of question and hurts another is visible.
- **Rate limit.** The runner waits 61 seconds and asks again on HTTP 429, up to 3 times. For local runs, `ASK_RATE_LIMIT_PER_MINUTE=0` in `.env` switches the limit off so nothing waits.

## Website

`frontend/` is a React site that reads the API in the browser. It is dark only. The look takes its cues from the official F1 site (big race cards, team colors, heavy wide type) and its data panels from lap analysis tools such as Garage61 (a timing tower beside the charts). Team color carries meaning: each race card and race header is shaded in the winning team's color, so a season reads as who won where. The type is one family, Archivo, used at three widths: extra-wide slanted headings in sentence case, normal body text, and narrow tabular numbers. Panels are rounded and lit from above, and there is one animation (the circuit draws itself once on the race page, and not at all with reduced motion).

| Decision | Why |
|---|---|
| React, TypeScript and Vite | Typed props catch wrong field names early, and Vite needs almost no setup. No server rendering, because the pages need no search ranking and the API is already the backend. |
| TanStack Query for fetching | It gives loading and error states, caching between pages, and one retry rule (network and 5xx errors only, never a 404). |
| Types generated from the API | `npm run gen:types` turns the API's OpenAPI document into `src/api-types.ts`, so the site cannot drift from `app/schemas.py` without a type error. The document is dumped from the app directly, so no server has to run. |
| CORS origins from `CORS_ORIGINS` | The allowed origins differ between local and a deployed site, so they are config. Only GET and POST with `Content-Type` are allowed, which is all the site uses. |
| Themes as CSS variables, Red Bull Racing by default | One `data-theme` plus variables on `<html>` recolor everything: background, panels, the page glow, the header stripe and buttons. Team colors were sampled from the 2026 team card artwork the user supplied. A test checks every theme's text against WCAG contrast (4.5:1 on background and panels) and its second color at 3:1, so a new theme cannot ship unreadable. |
| Race cards and headers shaded by the winning team | The deep team color fades into the panel, with speed streaks after the team card artwork. Text sits on the darkest end, and a test checks white text there at 4.5:1 for every team, including past winners such as Brawn and Renault. Races without a result are grey and have no link, because there is nothing to analyse yet. |
| A season strip above the cards | One block per round in the winner's team color, then wins per driver. It answers "who won this season" at a glance and is a quick way into any race. |
| Hovering a race card starts loading it | The race page's code, the race and its results are fetched on hover or focus, so the page usually opens with its data already there. |
| Circuit outlines and flags built in ahead of time | `npm run gen:circuits` turns the MIT-licensed bacinger/f1-circuits GeoJSON, pinned to one commit, into small SVG paths in `src/data/circuits.json` (23 kB), so the site downloads no map files. Flags come from flag-icons as SVG files, because Windows does not draw flag emoji. Only the 29 countries in use are bundled. |
| One listbox for the season and theme pickers | A native select opened a list of 27 seasons with small rows. The shared listbox shows 5 rows and scrolls, and follows the ARIA listbox keyboard pattern. Theme rows show the team's two colors next to the name. |
| Team colors fixed, theme colors separate | A chart line must mean the same team whatever theme is chosen. The theme colors the interface, never the data. Chart lines use brighter team colors than the cards, so a thin line reads on a dark panel. |
| A timing tower picks the drivers for the lap chart | The classification sits beside the charts, as in lap analysis tools. Clicking a row adds the driver to the lap chart; a fourth pick replaces the oldest, so picking never gets stuck. |
| Lap chart with a clean view by default and a raw view | Clean shows racing pace: it leaves out pit in and out laps, deleted laps, laps where the whole field was slow (safety car, red flag, rain) and laps over 107% of the driver's own median. Gaps of up to 3 laps are joined with a straight line, flagged so the tooltip skips them; longer gaps stay broken. There is no lower limit, because a race that turns dry has real fast laps (Norris's 1:22.167 in Australia 2025). Raw shows every timed lap with nothing cut off. The earlier single view clipped at 110% and left spikes and gaps that were hard to read. |
| Tire stints derived in the browser from laps | The API has no stint endpoint, and the laps already carry `stint_number` and `tire_type`. One pure function groups them, with unit tests. |
| A new stint on the same tire whose age keeps counting is merged into the one before | At the 2025 Australian GP the field drove through the pit lane under the safety car on laps 2 to 4, and OpenF1 recorded each pass as a new stint. 169 driver-races in the data have this pattern. The strategy chart shows those stops as pit lane passes, not tire stops. |
| Stints and pit stops in one strategy chart, rows in finishing order | The pit stop table was a list that was hard to read. One row per driver shows tires and stops together. A "Show as table" section keeps the same facts readable without the chart. |
| AI answers rendered from a small Markdown subset | The engineer writes bold labels and bullet lists, which showed as raw asterisks. A small reader in `src/markdown.ts` and `Markdown.tsx` handles paragraphs, lists, headings, bold, italic and code, and builds React elements. There is still no `dangerouslySetInnerHTML`, so an answer can never inject markup; a test checks that. |
| The browser holds the conversation | The page sends the last 3 completed questions and answers with each new one, so the engineer can ask "Which season?" and use the reply. Reloading the page starts over, and a hint says so. |
| No F1 or team logos | It is an unofficial fan project. Team names are plain text, and team colors are used for identification. |

## Known limits

- OpenF1's free tier returns 401 while any F1 session is live, so loads must run outside sessions. The API is unaffected because it reads from our own database.
- `laps.position` is derived from a time series of position changes. It matched Jolpica's official lap positions on 99.8% of laps at Monza 2023 and 98.8% at Zandvoort 2024. A driver's final lap is less reliable, so use `results` for finishing order.
- Pit stops are missing before the 2023 Spanish GP, and stationary times before the 2024 US GP, because OpenF1 doesn't have them.
- Results go back to 2000 and lap data to 2023, so career stats for drivers who started before 2000 are partial, and average lap time only covers 2023 onward.
- The analyst remembers only the last 3 questions and answers, and allows 8 lookups, so broad questions are turned away as too complex.
- It only knows what the tools return: results from 2000, and lap, tire and pit data from 2023. Its refusals for older data rely on the model following its instructions.
- Answers can vary between runs. Hard09 (two 2026 races in Spain) passed in both run-3 runs and missed once in run 4 with nothing changed for it. That is why every change is run twice, and why one miss is not tuned away.
- Refusal scoring relies on a list of phrases, so a correct refusal in new wording can fail until the list is extended. This happened with "doesn't include".
- The rate limit and daily spend cap are in memory. They reset on restart and would not be shared between several servers.
