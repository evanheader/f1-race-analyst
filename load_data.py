"""Load races, drivers, results, laps and pit stops into the database.

Usage: uv run python load_data.py [SEASON ...] [--round N]

Safe to run again: every write is an upsert, and raw API responses are cached in
cache/, so a rerun (or a run that stopped halfway) only fetches what is missing.
"""

import argparse
import bisect
import hashlib
import json
import os
import re
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert

from models import Driver, Lap, PitStop, Race, Result

JOLPICA = "https://api.jolpi.ca/ergast/f1"
OPENF1 = "https://api.openf1.org/v1"
HEADERS = {"User-Agent": "f1-race-analyst/0.1.0"}
CACHE_DIR = Path("cache")

# Jolpica allows 4 requests per second; stay well under it.
JOLPICA_DELAY = 0.5
OPENF1_DELAY = 0.3

DELETED_LAP = re.compile(r"CAR (\d+) .*DELETED.* LAP (\d+)")


class RetryLater(Exception):
    """The service is rate limiting us or locked by a live session."""


def get_json(url: str, delay: float):
    """GET a URL as JSON, reading from and writing to the cache."""
    path = CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest()[:20] + ".json")
    if path.exists():
        return json.loads(path.read_text())

    time.sleep(delay)
    response = requests.get(url, headers=HEADERS, timeout=60)
    # OpenF1 has an undocumented burst limit. Wait it out a few times before giving up.
    for wait in (5, 15, 45):
        if response.status_code != 429 or not url.startswith(OPENF1):
            break
        time.sleep(wait)
        response = requests.get(url, headers=HEADERS, timeout=60)
    if response.status_code in (401, 429):
        raise RetryLater(f"{response.status_code} from {url}. Try again later.")
    if response.status_code == 404:
        # OpenF1 answers 404 {"detail": "No results found."} for an empty result.
        data = []
    else:
        response.raise_for_status()
        data = response.json()

    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def jolpica_pages(path: str) -> list[dict]:
    """All Races[] entries for a Jolpica path, following limit/offset paging."""
    races = []
    offset = 0
    while True:
        data = get_json(f"{JOLPICA}/{path}?limit=100&offset={offset}", JOLPICA_DELAY)["MRData"]
        races.extend(data["RaceTable"]["Races"])
        offset += int(data["limit"])
        if offset >= int(data["total"]):
            return races


def openf1(endpoint: str, session_key: int) -> list[dict]:
    return get_json(f"{OPENF1}/{endpoint}?session_key={session_key}", OPENF1_DELAY)


def upsert(conn, table, rows: list[dict], key: list[str]) -> None:
    """Insert rows, or update them if a row with the same key already exists."""
    if not rows:
        return
    stmt = insert(table)
    update = {c.name: stmt.excluded[c.name] for c in table.__table__.columns
              if c.name != "id" and c.name not in key}
    conn.execute(stmt.on_conflict_do_update(index_elements=key, set_=update), rows)


def load_races(conn, season: int) -> None:
    """Calendar from Jolpica, each race matched to its OpenF1 session by UTC date."""
    sessions = get_json(f"{OPENF1}/sessions?year={season}&session_name=Race", OPENF1_DELAY)
    session_by_date = {s["date_start"][:10]: s["session_key"] for s in sessions}

    rows = []
    for race in jolpica_pages(f"{season}/races/"):
        session_key = session_by_date.get(race["date"])
        if session_key is None:
            # Night races (Las Vegas) start after midnight UTC, so OpenF1's date is a day later.
            next_day = (date.fromisoformat(race["date"]) + timedelta(days=1)).isoformat()
            session_key = session_by_date.get(next_day)
        if session_key is None:
            print(f"  no OpenF1 session for {season} round {race['round']} ({race['date']})")
        rows.append({
            "season": int(race["season"]),
            "round": int(race["round"]),
            "name": race["raceName"],
            "date": datetime.strptime(race["date"], "%Y-%m-%d").date(),
            "circuit_ref": race["Circuit"]["circuitId"],
            "openf1_session_key": session_key,
        })
    upsert(conn, Race, rows, ["season", "round"])
    print(f"{season}: {len(rows)} races")


def load_results(conn, season: int) -> None:
    """Drivers and results for a whole season from Jolpica."""
    races = jolpica_pages(f"{season}/results/")
    race_ids = {
        (r.season, r.round): r.id
        for r in conn.execute(Race.__table__.select().where(Race.season == season))
    }

    drivers = {}
    for race in races:
        for result in race["Results"]:
            d = result["Driver"]
            drivers[d["driverId"]] = {
                "driver_ref": d["driverId"],
                "code": d.get("code"),
                "full_name": f"{d['givenName']} {d['familyName']}",
            }
    upsert(conn, Driver, list(drivers.values()), ["driver_ref"])
    driver_ids = {
        d.driver_ref: d.id
        for d in conn.execute(Driver.__table__.select().where(Driver.driver_ref.in_(drivers)))
    }

    rows = []
    for race in races:
        for r in race["Results"]:
            rows.append({
                "race_id": race_ids[(season, int(race["round"]))],
                "driver_id": driver_ids[r["Driver"]["driverId"]],
                "driver_number": int(r["number"]),
                "team": r["Constructor"]["name"],
                "grid": int(r["grid"]),
                "position": int(r["position"]),
                "position_text": r["positionText"],
                "status": r["status"],
                "points": Decimal(r["points"]),
            })
    upsert(conn, Result, rows, ["race_id", "driver_id"])
    print(f"{season}: {len(drivers)} drivers, {len(rows)} results")


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text)


def position_at_lap_ends(laps: list[dict], changes: list[dict]) -> dict[int, int | None]:
    """A driver's position at the end of each lap (lap_number -> position).

    OpenF1 gives position as a time series of changes. The end of a lap is the next
    lap's start, or the lap's own start plus its duration for the last lap. The
    position is the latest change at or before that moment.
    """
    times = [parse_time(c["date"]) for c in changes]
    by_lap = {lap["lap_number"]: lap for lap in laps}
    result = {}
    for number, lap in by_lap.items():
        following = by_lap.get(number + 1)
        if following is not None:
            end = parse_time(following["date_start"])
        elif lap["lap_duration"] is not None:
            end = parse_time(lap["date_start"]).timestamp() + lap["lap_duration"]
            end = datetime.fromtimestamp(end, tz=parse_time(lap["date_start"]).tzinfo)
        else:
            result[number] = None
            continue
        i = bisect.bisect_right(times, end)
        result[number] = changes[i - 1]["position"] if i else None
    return result


def load_race_laps(conn, race, driver_by_number: dict[int, int]) -> None:
    """Laps and pit stops for one race from OpenF1."""
    key = race.openf1_session_key
    laps = openf1("laps", key)
    stints = openf1("stints", key)
    positions = openf1("position", key)
    control = openf1("race_control", key)
    pits = openf1("pit", key)

    deleted = set()
    for message in control:
        match = DELETED_LAP.search(message["message"])
        if match:
            deleted.add((int(match.group(1)), int(match.group(2))))

    laps_by_car = {}
    for lap in laps:
        laps_by_car.setdefault(lap["driver_number"], []).append(lap)

    lap_rows = []
    for car, car_laps in laps_by_car.items():
        if car not in driver_by_number:
            print(f"  skipping car {car}: not in the results")
            continue
        car_stints = [s for s in stints if s["driver_number"] == car]
        car_positions = sorted(
            (p for p in positions if p["driver_number"] == car), key=lambda p: p["date"]
        )
        position_by_lap = position_at_lap_ends(car_laps, car_positions)

        for lap in car_laps:
            number = lap["lap_number"]
            stint = next(
                (s for s in car_stints
                 if s["lap_start"] <= number <= (s["lap_end"] or number)),
                None,
            )
            duration = lap["lap_duration"]
            lap_rows.append({
                "race_id": race.id,
                "driver_id": driver_by_number[car],
                "lap_number": number,
                "lap_time_seconds": None if duration is None else Decimal(str(duration)),
                "tire_type": stint["compound"] if stint else None,
                "tire_age": (stint["tyre_age_at_start"] + number - stint["lap_start"]) if stint else None,
                "stint_number": stint["stint_number"] if stint else None,
                "position": position_by_lap[number],
                "is_pit_out_lap": bool(lap["is_pit_out_lap"]),
                "is_deleted": (car, number) in deleted,
            })

    pit_rows = {}
    for pit in pits:
        if pit["driver_number"] not in driver_by_number or pit["lane_duration"] is None:
            continue
        stationary = pit["stop_duration"]
        # A repeated (driver, lap) keeps the last row, so the upsert never sees the key twice.
        pit_rows[(pit["driver_number"], pit["lap_number"])] = {
            "race_id": race.id,
            "driver_id": driver_by_number[pit["driver_number"]],
            "lap_number": pit["lap_number"],
            "lane_seconds": Decimal(str(pit["lane_duration"])),
            "stationary_seconds": None if stationary is None else Decimal(str(stationary)),
        }

    upsert(conn, Lap, lap_rows, ["race_id", "driver_id", "lap_number"])
    upsert(conn, PitStop, list(pit_rows.values()), ["race_id", "driver_id", "lap_number"])
    print(f"  {race.season} round {race.round}: {len(lap_rows)} laps, {len(pit_rows)} pit stops")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("seasons", nargs="*", type=int, default=[2023, 2024])
    parser.add_argument("--round", type=int, help="load laps and pit stops for this round only")
    args = parser.parse_args()

    load_dotenv()
    engine = create_engine(os.environ["DATABASE_URL"])

    for season in args.seasons:
        try:
            # One transaction per step: a crash never leaves half a race behind.
            with engine.begin() as conn:
                load_races(conn, season)
            with engine.begin() as conn:
                load_results(conn, season)

            with engine.connect() as conn:
                races = conn.execute(
                    Race.__table__.select()
                    .where(Race.season == season, Race.openf1_session_key.is_not(None))
                    .order_by(Race.round)
                ).all()
            for race in races:
                if args.round and race.round != args.round:
                    continue
                with engine.begin() as conn:
                    driver_by_number = {
                        r.driver_number: r.driver_id
                        for r in conn.execute(Result.__table__.select().where(Result.race_id == race.id))
                    }
                    load_race_laps(conn, race, driver_by_number)
        except RetryLater as error:
            raise SystemExit(f"Stopped: {error} Rerun later; cached responses are reused.")


if __name__ == "__main__":
    main()
