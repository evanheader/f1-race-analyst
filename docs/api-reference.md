# API reference: OpenF1 and Jolpica

Working notes on the two data sources this project loads from. They are summaries of the upstream docs, checked on 2026-10-30. The upstream docs win when they disagree with this file.

- OpenF1 docs: https://openf1.org/docs/ (source: https://github.com/br-g/openf1)
- Jolpica docs: https://github.com/jolpica/jolpica-f1/tree/main/docs (source: https://github.com/jolpica/jolpica-f1)
- How the two map onto our tables: [schema.md](schema.md)

| | OpenF1 | Jolpica (`jolpica-f1`) |
|---|---|---|
| Base URL | `https://api.openf1.org/v1/{endpoint}` | `https://api.jolpi.ca/ergast/f1/...` |
| Covers | Telemetry, timing, laps, stints, pit, weather, race control | Results, schedules, standings, drivers, circuits, constructors |
| History | 2023 onward | 1950 onward (laps from 1996, pit stops from 2011) |
| Auth | None for historical data. Live data needs a paid plan | None. A custom `User-Agent` header is required |
| Format | JSON (default) or CSV (`csv=true`) | JSON only (no XML) |
| Values | Typed JSON (numbers are numbers) | Everything is a string |
| Role here | Lap-level data | Race results and race details |

---

## Part 1: OpenF1

An open-source, unofficial API for F1 timing and session data. It is not affiliated with the Formula 1 companies.

### Access and limits

- Historical data (2023 onward) needs no authentication. Real-time data needs a paid subscription.
- The docs page does not state rate limits.
- **Project gotcha:** free access returns 401 for all data, including past races, while any F1 session is live (see [schema.md](schema.md#decisions)). Treat 401 as retry-later and run loaders outside sessions.

### Query syntax

Parameters go on the query string. Any attribute except arrays can be a filter.

| Feature | Syntax | Example |
|---|---|---|
| Equality | `field=value` | `driver_number=55` |
| Comparison | `>`, `>=`, `<`, `<=` | `lap_duration>=120` |
| Multiple values | Repeat the parameter | `driver_number=4&driver_number=81` |
| Latest | `latest` for `meeting_key` and `session_key` | `session_key=latest` |
| Time filter | `date`, `date_start`, `date_end` with a comparison | `date>=2023-09-01` |
| CSV output | `csv=true` | `/v1/sessions?year=2023&csv=true` |

- Dates accept anything Python's `dateutil.parser.parse` reads: `2021-09-10`, `2021-09-10T14:30:20+00:00`, `10 September 2021`.
- URL-encode spaces and special characters: `session_name=Sprint%20Qualifying`.
- The comparison operators are literal characters in the query string, so use `requests` with a pre-built URL or `params` carefully. `requests` would encode `>=` in a dict key.

Example requests:

```
/v1/laps?session_key=9222&driver_number=55&is_pit_out_lap=true&lap_duration>=120
/v1/sessions?date_start>=2023-09-01&date_end<=2023-09-30
```

### Identifiers

Almost every endpoint carries these.

| Field | Meaning |
|---|---|
| `meeting_key` | A Grand Prix or testing weekend. Accepts `latest` |
| `session_key` | One session in a meeting (practice, qualifying, race). Accepts `latest`. This is what `races.openf1_session_key` stores |
| `driver_number` | Car number for that season. OpenF1 has no other driver ID, which is why `results.driver_number` exists |

### Endpoints

Types are inferred from sample responses. The docs do not state them.

#### `meetings`

A Grand Prix or testing weekend. Updated daily at midnight UTC.
Example: `/v1/meetings?year=2026&country_name=Singapore`

| Field | Type | Description |
|---|---|---|
| `meeting_key` | int | Meeting ID |
| `meeting_name` | string | Meeting name |
| `meeting_official_name` | string | Official name |
| `year` | int | Season |
| `date_start`, `date_end` | ISO 8601 | UTC start and end |
| `gmt_offset` | `HH:MM:SS` | Local offset from GMT |
| `is_cancelled` | bool | Whether it was cancelled |
| `location` | string | City or place |
| `country_key`, `country_code`, `country_name` | int, string, string | Country |
| `country_flag` | URL | Flag image |
| `circuit_key`, `circuit_short_name` | int, string | Circuit |
| `circuit_type` | string | `Permanent`, `Temporary - Street` or `Temporary - Road` |
| `circuit_image` | URL | Circuit image |
| `circuit_info_url` | URL | JSON of detailed circuit info (MultiViewer data) |

#### `sessions`

Sessions within a meeting. Updated daily at midnight UTC.
Example: `/v1/sessions?country_name=Belgium&session_name=Sprint%20Qualifying&year=2023`

| Field | Type | Description |
|---|---|---|
| `session_key`, `meeting_key` | int | IDs |
| `session_name` | string | For example `Practice 1`, `Qualifying`, `Race` |
| `session_type` | string | For example `Practice`, `Qualifying`, `Race` |
| `date_start`, `date_end` | ISO 8601 | UTC start and end |
| `gmt_offset` | `HH:MM:SS` | Local offset from GMT |
| `is_cancelled` | bool | Whether it was cancelled |
| `year` | int | Season |
| `location`, `country_key`, `country_code`, `country_name` | | Where it was held |
| `circuit_key`, `circuit_short_name` | | Circuit |

#### `drivers`

Driver details per session.
Example: `/v1/drivers?driver_number=1&session_key=9158`

| Field | Type | Description |
|---|---|---|
| `driver_number` | int | Car number |
| `broadcast_name` | string | Name as shown on TV |
| `full_name`, `first_name`, `last_name` | string | Names |
| `name_acronym` | string | Three-letter code, for example VER |
| `team_name` | string | Team |
| `team_colour` | string | Hex `RRGGBB`, no `#` |
| `headshot_url` | URL | Photo |
| `country_code` | string | **Deprecated**, removed after the 2026 season |
| `meeting_key`, `session_key` | int | IDs |

#### `laps`

Per-lap details. Feeds `laps.lap_number`, `lap_time_seconds` and `is_pit_out_lap`.
Example: `/v1/laps?session_key=9161&driver_number=63&lap_number=8`

| Field | Type | Description |
|---|---|---|
| `lap_number` | int | Starts at 1 |
| `lap_duration` | number | Lap time in seconds. May be missing for some laps |
| `duration_sector_1`, `_2`, `_3` | number | Sector times in seconds |
| `date_start` | ISO 8601 | Approximate UTC lap start |
| `is_pit_out_lap` | bool | True for out-laps |
| `i1_speed`, `i2_speed` | int | Speed (km/h) at the intermediate points |
| `st_speed` | int | Speed trap (km/h) |
| `segments_sector_1`, `_2`, `_3` | int[] | Mini-sector status codes (below) |
| `driver_number`, `meeting_key`, `session_key` | int | IDs |

Segment codes: `0` not available, `2048` yellow, `2049` green, `2051` purple, `2064` pit lane, `2050`/`2052`/`2068` unknown. Segments are unavailable during races, and colours may not match TV graphics.

#### `stints`

Continuous runs by a driver. Feeds `laps.tire_type`, `tire_age` and `stint_number`.
Example: `/v1/stints?session_key=9165&tyre_age_at_start>=3`

| Field | Type | Description |
|---|---|---|
| `stint_number` | int | Starts at 1 |
| `lap_start`, `lap_end` | int | First and last lap of the stint |
| `compound` | string | `SOFT`, `MEDIUM`, `HARD` and so on |
| `tyre_age_at_start` | int | Laps already on the tyre at stint start |
| `driver_number`, `meeting_key`, `session_key` | int | IDs |

Tyre age on a given lap is `tyre_age_at_start + (lap_number - lap_start)`.

#### `pit`

Cars entering and moving through the pit lane. Feeds the `pit_stops` table.
Example: `/v1/pit?session_key=9877&stop_duration<2.3`

Coverage: no data before the 2023 Spanish GP (round 7). Earlier sessions return 404 "No results found." Observed on 2026-10-30, not stated in the docs.

| Field | Type | Description |
|---|---|---|
| `lap_number` | int | Lap of the stop |
| `lane_duration` | number | Seconds in the pit lane |
| `stop_duration` | number | Stationary seconds. Only from the 2024 US GP onward |
| `pit_duration` | number | **Deprecated**, same as `lane_duration`. Removed after the 2026 season |
| `date` | ISO 8601 | UTC timestamp |
| `driver_number`, `meeting_key`, `session_key` | int | IDs |

#### `position`

Driver positions through a session, including the initial placement. This is a time series of changes, not one row per lap.
Example: `/v1/position?meeting_key=1217&driver_number=40&position<=3`

| Field | Type | Description |
|---|---|---|
| `position` | int | Starts at 1 |
| `date` | ISO 8601 | UTC timestamp of the change |
| `driver_number`, `meeting_key`, `session_key` | int | IDs |

#### `race_control`

Session status, incidents, flags, safety car and deleted lap times. Feeds `laps.is_deleted`.
Example: `/v1/race_control?flag=BLACK AND WHITE&driver_number=1&date>=2023-01-01&date<2023-09-01`

| Field | Type | Description |
|---|---|---|
| `category` | string | `SessionStatus`, `CarEvent`, `Drs`, `Flag`, `SafetyCar` and so on |
| `flag` | string or null | `GREEN`, `YELLOW`, `DOUBLE YELLOW`, `CHEQUERED` and so on |
| `scope` | string | `Track`, `Driver`, `Sector` and so on |
| `message` | string | Free text |
| `lap_number` | int or null | Lap in a race |
| `driver_number` | int or null | Driver involved |
| `sector` | int or null | Mini-sector |
| `qualifying_phase` | int or null | 1, 2 or 3 |
| `date` | ISO 8601 | UTC timestamp |
| `meeting_key`, `session_key` | int | IDs |

For deleted laps the car and lap come from the `message` text, not the structured fields. See [schema.md](schema.md#laps).

#### `session_result`

Final standings for a session. Available a few minutes after official publication.
Example: `/v1/session_result?session_key=7782&position<=3`

| Field | Type | Description |
|---|---|---|
| `position` | int | Final position |
| `driver_number` | int | Car number |
| `number_of_laps` | int | Laps completed |
| `duration` | number or number[] | Best lap or race time in seconds. Qualifying returns `[Q1, Q2, Q3]` |
| `gap_to_leader` | number, string or array | Seconds, or `+N LAP(S)`. Qualifying returns an array |
| `dnf`, `dns` | bool | Only true in qualifying or race sessions |
| `dsq` | bool | Disqualified |
| `meeting_key`, `session_key` | int | IDs |

#### `starting_grid`

Grid for the upcoming race. Available a few minutes after official publication.
Example: `/v1/starting_grid?session_key=7783&position<=3`

| Field | Type | Description |
|---|---|---|
| `position` | int | Grid position |
| `lap_duration` | number | Qualifying lap time in seconds |
| `driver_number`, `meeting_key`, `session_key` | int | IDs |

#### `intervals`

Gaps between drivers and to the leader. Races only, updated about every 4 seconds.
Example: `/v1/intervals?session_key=9165&interval>0&interval<0.005`

| Field | Type | Description |
|---|---|---|
| `gap_to_leader` | number, string or null | Seconds, `+1 LAP` if lapped, null for the leader |
| `interval` | number, string or null | Gap to the car ahead, same format |
| `date` | ISO 8601 | UTC timestamp |
| `driver_number`, `meeting_key`, `session_key` | int | IDs |

#### `overtakes`

Position exchanges between two drivers, including pit stop and post-race penalty changes. Races only and may be incomplete.
Example: `/v1/overtakes?session_key=9636&overtaking_driver_number=63&overtaken_driver_number=4&position=1`

| Field | Type | Description |
|---|---|---|
| `overtaking_driver_number` | int | Driver who passed |
| `overtaken_driver_number` | int | Driver who was passed |
| `position` | int | Passer's position after the move |
| `date` | ISO 8601 | UTC timestamp |
| `meeting_key`, `session_key` | int | IDs |

#### `championship_drivers` (beta)

Driver standings. Race sessions only.
Example: `/v1/championship_drivers?session_key=9839&driver_number=4&driver_number=81`

| Field | Type | Description |
|---|---|---|
| `points_start`, `points_current` | int | Points before the race, and during or after it |
| `position_start`, `position_current` | int | Standing before the race, and during or after it |
| `driver_number`, `meeting_key`, `session_key` | int | IDs |

"Current" depends on when you call.

#### `championship_teams` (beta)

Same as `championship_drivers`, with `team_name` (string) in place of `driver_number`.
Example: `/v1/championship_teams?session_key=9839&team_name=McLaren`

#### `car_data`

Car telemetry at about 3.7 Hz.
Example: `/v1/car_data?driver_number=55&session_key=9159&speed>=315`

| Field | Type | Description |
|---|---|---|
| `speed` | int | km/h |
| `rpm` | int | Engine RPM |
| `n_gear` | int | 1 to 8, `0` is neutral or none |
| `throttle` | int | 0 to 100 |
| `brake` | int | `100` pressed, `0` not |
| `drs` | int | Status code (below) |
| `date` | ISO 8601 | UTC timestamp |
| `driver_number`, `meeting_key`, `session_key` | int | IDs |

DRS codes (from FastF1, partly unknown): `0`, `1` off; `8` detected, eligible in the zone; `10`, `12`, `14` on; `2`, `3`, `9` unknown.

#### `location`

Approximate car position on track at about 3.7 Hz. It shows progress around the track, not lateral position. The origin (0, 0, 0) is arbitrary.
Example: `/v1/location?session_key=9161&driver_number=81&date>2023-09-16T13:03:35.200&date<2023-09-16T13:03:35.800`

Fields: `x`, `y`, `z` (int), `date`, `driver_number`, `meeting_key`, `session_key`.

#### `weather`

Track weather, updated about every minute.
Example: `/v1/weather?meeting_key=1208&wind_direction>=130&track_temperature>=52`

| Field | Type | Description |
|---|---|---|
| `air_temperature`, `track_temperature` | number | °C |
| `humidity` | int | Percent |
| `pressure` | number | mbar |
| `rainfall` | int | Rainfall indicator |
| `wind_speed` | number | m/s |
| `wind_direction` | int | Degrees, 0 to 359 |
| `date`, `meeting_key`, `session_key` | | Timestamp and IDs |

#### `team_radio`

A selection of driver-team radio clips. Coverage dropped sharply from 2026, mostly due to F1's release policy.
Example: `/v1/team_radio?session_key=9158&driver_number=11`

Fields: `recording_url` (MP3 URL), `date`, `driver_number`, `meeting_key`, `session_key`.

### Deprecations to avoid

- `pit.pit_duration`: use `lane_duration`.
- `drivers.country_code`: gone after the 2026 season.

---

## Part 2: Jolpica

An open-source F1 API that replaces the Ergast API and keeps its URLs and response shapes. All paths start with `/ergast/f1/`. Use `https://api.jolpi.ca` as the host. The upstream docs only state this host in the per-endpoint pages.

### Required User-Agent

A custom `User-Agent` is required. Use an app name plus version so a bad version can be blocked on its own, and add other relevant libraries.

```
User-Agent: f1-race-analyst/0.1.0
```

FastF1 users prepend theirs to `fastf1.ergast.interface.HEADERS["User-Agent"]`.

### Rate limits

| Limit | Unauthenticated |
|---|---|
| Burst | 4 requests per second |
| Sustained | 500 requests per hour |

- Exceeding either returns `429 Too Many Requests` ("Request was throttled."). IP-sharing counts against you.
- These limits are subject to change and will go down as token access and a replacement API roll out. Tokens are not yet available.
- No rate-limit headers are documented.
- Upstream advice: cache results, and prefer filtered, paged queries over many small ones. For example `2024/12/laps.json?limit=100&offset=0`, or `2024/drivers/hamilton/results.json` for a season's results.
- At 500 per hour a full backfill needs pacing, local caching and resumable loads.

### URL rules

- End every URL with `/` or `.json`.
- Route filters follow a fixed order. `season` must come first after `/ergast/f1/`, and `round` must directly follow it. Other filters (`drivers/{id}`, `circuits/{id}`, `constructors/{id}`, `grid/{n}`, `fastest/{n}`, `status/{id}`, `results/{n}`) then follow. The resource name goes last.
- `season` accepts a year or `current`. `round` accepts `1` to `n` or `last`, and `next` on some endpoints (races, circuits, qualifying).
- If a filter is repeated, only the last one is used. Ergast returned a 400.

### Pagination

| Param | Default | Max |
|---|---|---|
| `limit` | 30 | 100 |
| `offset` | 0 | |

Loop until `offset + limit >= total`. Always check `MRData.limit`, which may differ from what you asked for. One season of laps is thousands of rows, so use `limit=100`.

### Response envelope

Every response:

```json
{
  "MRData": {
    "xmlns": "",
    "series": "f1",
    "url": "http://api.jolpi.ca/ergast/f1/2021/9/results/",
    "limit": "30",
    "offset": "0",
    "total": "20",
    "RaceTable": { "season": "2021", "round": "9", "Races": [] }
  }
}
```

The table key depends on the endpoint: `RaceTable`, `DriverTable`, `CircuitTable`, `ConstructorTable`, `SeasonTable`, `StatusTable` or `StandingsTable`. All numbers, including `total`, are strings.

### Differences from Ergast

Intentional and permanent.

- No XML.
- `positionText` uses `R` instead of `N` for retirements.
- `Time.time` always has three decimals, zero-padded.
- Standings need a season.
- 2023: the Sprint Shootout is `SprintShootout` (Ergast called it `SecondPractice`).
- 2024 onward: Sprint Qualifying is `SprintQualifying` (Ergast: `SecondPractice`).
- `status` values changed. From 2025 all retirements and accidents are "Retired", because no source distinguishes them.
- Status results are ordered by count, not `statusId`.

### Endpoints

Paths are relative to `https://api.jolpi.ca/ergast/f1`.

#### Races: `/races/`

Schedule, earliest to latest. Our `races` table comes from this.

| Pattern | Purpose |
|---|---|
| `/races/` | All races in history |
| `/{season}/races/` | One season |
| `/{season}/{round}/races/` | One round (`last`, `next` allowed) |
| `/circuits/{circuitId}/races/` | At a circuit |
| `/drivers/{driverId}/races/` | Featuring a driver |
| `/constructors/{constructorId}/races/` | Featuring a constructor |
| `/grid/{n}/races/`, `/status/{id}/races/` | By grid position or status |

Race object:

| Field | Always | Description |
|---|:---:|---|
| `season`, `round` | yes | |
| `raceName` | yes | For example "Italian Grand Prix" |
| `Circuit` | yes | `circuitId`, `url`, `circuitName`, `Location` (`lat`, `long`, `locality`, `country`) |
| `date` | yes | `YYYY-MM-DD` |
| `url` | no | Wikipedia |
| `time` | no | UTC start, for example `15:00:00Z`. Missing for old races |
| `FirstPractice`, `SecondPractice`, `ThirdPractice`, `Qualifying` | no | `{date, time}` |
| `Sprint` | no | `{date, time}` |
| `SprintQualifying` / `SprintShootout` | no | `{date, time}`, 2024+ and 2023 |

`date` + `time` here can differ from OpenF1's session start. See the matching rule in [schema.md](schema.md#decisions).

#### Results: `/results/`

Race results. Our `results` table comes from this.

| Pattern | Purpose |
|---|---|
| `/{season}/results/` | Season |
| `/{season}/{round}/results/` | One race (`last` allowed) |
| `/{season}/drivers/{driverId}/results/` | A driver's season |
| `/circuits/{id}/results/`, `/constructors/{id}/results/`, `/drivers/{id}/results/` | By entity |
| `/{season}/fastest/{rank}/results/` | By fastest lap rank |
| `/{season}/grid/{n}/results/` | By grid slot |
| `/status/{id}/results/` | By status |

Result object (inside `Races[].Results[]`):

| Field | Always | Description |
|---|:---:|---|
| `number` | yes | Car number. Our link to OpenF1 |
| `position` | yes | Numeric order |
| `positionText` | yes | `1`, `R`, `W` and so on. Read it with `position` |
| `points` | yes | String, can be fractional (12.5) |
| `Driver` | yes | `driverId`, `permanentNumber`, `code`, `url`, `givenName`, `familyName`, `dateOfBirth`, `nationality` |
| `Constructor` | no | `constructorId`, `url`, `name`, `nationality` |
| `grid` | no | Starting slot |
| `laps` | no | Laps completed |
| `status` | no | For example `Finished`, `Lapped`, `Retired` |
| `Time` | no | `{millis, time}` |
| `FastestLap` | no | `{rank, lap, Time: {time}, AverageSpeed: {units, speed}}` |

```json
{
  "number": "33", "position": "1", "positionText": "1", "points": "26",
  "Driver": { "driverId": "max_verstappen", "permanentNumber": "33", "code": "VER",
              "givenName": "Max", "familyName": "Verstappen", "dateOfBirth": "1997-09-30", "nationality": "Dutch" },
  "Constructor": { "constructorId": "red_bull", "name": "Red Bull", "nationality": "Austrian" },
  "grid": "1", "laps": "71", "status": "Finished",
  "Time": { "millis": "5034543", "time": "1:23:54.543" },
  "FastestLap": { "rank": "1", "lap": "62", "Time": { "time": "1:06.200" },
                  "AverageSpeed": { "units": "kph", "speed": "234.815" } }
}
```

#### Sprint: `/sprint/`

Sprint results. Same filters as results (`/{season}/{round}/sprint/`, `/drivers/{id}/sprint/` and so on). Rows sit in `Races[].SprintResults[]` with the same fields as a result. The project does not load sprints yet.

#### Qualifying: `/qualifying/`

`/{season}/{round}/qualifying/` and the usual entity filters. Rows sit in `Races[].QualifyingResults[]`.

| Field | Description |
|---|---|
| `number`, `position` | Car number and qualifying position |
| `Driver`, `Constructor` | Objects, as above |
| `Q1`, `Q2`, `Q3` | `m:ss.sss`, omitted if the driver did not run |

`grid/{n}` matches the race start slot, not qualifying position.

#### Laps: `/{season}/{round}/laps/`

Lap times, from 1996. Season and round are required.

| Pattern | Purpose |
|---|---|
| `/{season}/{round}/laps/` | All laps |
| `/{season}/{round}/laps/{lapNumber}/` | One lap for every driver |
| `/{season}/{round}/drivers/{driverId}/laps/` | One driver |
| `/{season}/{round}/constructors/{constructorId}/laps/` | One constructor |

Shape: `Races[].Laps[]` with `number`, and `Timings[]` of `{driverId, position, time}` (`time` like `1:24.350`). `limit` counts timings, not laps, so a 58-lap race with 20 drivers is about 1,160 rows. This is the Jolpica-side source for pre-2023 lap times, but we use OpenF1 for laps.

#### Pit stops: `/{season}/{round}/pitstops/`

From 2011.

| Pattern | Purpose |
|---|---|
| `/{season}/{round}/pitstops/` | All stops |
| `/{season}/{round}/pitstops/{stopNumber}` | The nth stop per driver |
| `/{season}/{round}/drivers/{driverId}/pitstops/` | One driver |
| `/{season}/{round}/laps/{lapNumber}/pitstops` | Stops on a lap |

Shape: `Races[].PitStops[]` of `{driverId, lap, stop, time, duration}`. `time` is time of day (`HH:mm:ss`). `duration` is the whole pit lane time in `ss.sss`, or `m:ss.sss` for red flag stops. Upstream's own example shows a bogus `40:55.302`, so check for outliers. We use OpenF1 `pit` instead.

#### Drivers: `/drivers/`

`/drivers/`, `/{season}/drivers/`, `/{season}/{round}/drivers/`, `/drivers/{driverId}/`, plus filters by circuit, constructor, fastest, grid, results and status.

Driver object: `driverId` (always), `givenName`, `familyName` (always), and optional `permanentNumber`, `code`, `url`, `dateOfBirth`, `nationality`. `driverId` is a slug like `max_verstappen`, and is what `drivers.driver_ref` stores. `code` is optional and not unique.

#### Constructors: `/constructors/`

`/constructors/`, `/{season}/constructors/`, `/{season}/{round}/constructors/`, `/constructors/{constructorId}/`, plus filters by circuit, driver, fastest, grid, results and status.

Fields: `name` (always), `constructorId`, `url`, `nationality`.

#### Circuits: `/circuits/`

`/circuits/` (alphabetical by `circuitId`), `/{season}/circuits/`, `/{season}/{round}/circuits/`, `/circuits/{circuitId}/`, plus filters by constructor, driver, fastest, grid, results and status.

Fields: `circuitId` (for example `monza`), `url`, `circuitName`, `Location` (`lat`, `long`, `locality`, `country`).

#### Seasons: `/seasons/`

`/seasons/`, `/{season}/seasons/`, and filters by circuit, constructor, driver, grid and status. Fields: `season`, `url`.

#### Status: `/status/`

`/status/`, `/{season}/status/`, `/{season}/{round}/status/`, and filters by circuit, constructor, driver, grid, results and fastest. Rows are `{statusId, count, status}` in `StatusTable.Status`, ordered by count descending.

Stable IDs: `1` Finished, `2` Disqualified, `3` Accident, `31` Retired, `143` Lapped. IDs before 2024 may change, and `3` is not implemented for newer seasons, so some `31`s may become `3`.

#### Driver standings: `/{season}/driverstandings/`

| Pattern | Purpose |
|---|---|
| `/{season}/driverstandings/` | Final (or latest) standings |
| `/{season}/{round}/driverstandings/` | After a round |
| `/{season}/drivers/{driverId}/driverstandings/` | One driver |
| `/{season}/driverstandings/{position}/` | One position |

Shape: `StandingsTable.StandingsLists[].DriverStandings[]` with `position`, `positionText` (`E`, `D`, `-` or a number), `points`, `wins`, `Driver`, and `Constructors[]` (every team that season).

#### Constructor standings: `/{season}/constructorstandings/`

Same patterns with `constructorstandings` and `/constructors/{id}/`. Rows are `StandingsLists[].ConstructorStandings[]` with `position`, `positionText`, `points`, `wins`, `Constructor`.

---

## Part 3: Using them together

- **Link key:** Jolpica `results[].number` equals OpenF1 `driver_number` for the same season. Neither is stable across seasons (NOR is #1 in 2026), so never key a driver on it alone.
- **Matching races:** OpenF1 `sessions` where `session_name = "Race"` against Jolpica `races` by year and UTC date, not time. Start times differ between the sources.
- **Race only:** filter OpenF1 to `session_name=Race`. Sprint sessions have `session_name = "Sprint"`.
- **Scope of history:** OpenF1 starts in 2023, so earlier races only get Jolpica data.
- **Types:** Jolpica returns strings for everything. Cast on load, using `NUMERIC` for `points`.
- **Order of loading:** Jolpica `races`, `drivers` and `results` first, then OpenF1 `sessions`, `laps`, `stints`, `position`, `pit` and `race_control`, joined through `driver_number`.
- **Politeness:** cache raw responses on disk. Jolpica's 500 per hour is the tighter limit.

## Open items

Not verified against live responses. Check these before relying on them.

- OpenF1 rate limits are undocumented.
- Whether Jolpica supports `next` on every endpoint. Upstream says so only for races, circuits and qualifying.
- The base URL `https://api.openf1.org/v1` is inferred from the docs' example requests.
- Jolpica's own docs contain a few typos (for example `positonText` in constructor standings), so trust the sample responses.
