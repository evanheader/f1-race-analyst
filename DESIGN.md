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

## Known limits

- OpenF1's free tier returns 401 while any F1 session is live, so loads must run outside sessions. The API is unaffected because it reads from our own database.
- `laps.position` is derived from a time series of position changes. It matched Jolpica's official lap positions on 99.8% of laps at Monza 2023 and 98.8% at Zandvoort 2024. A driver's final lap is less reliable, so use `results` for finishing order.
- Pit stops are missing before the 2023 Spanish GP, and stationary times before the 2024 US GP, because OpenF1 doesn't have them.
- Results go back to 2000 and lap data to 2023, so career stats for drivers who started before 2000 are partial, and average lap time only covers 2023 onward.
