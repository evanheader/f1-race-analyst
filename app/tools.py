"""The tools Claude can call to read race data. All of them only run SELECTs.

Every tool identifies things the way a person would (season + race name, driver name),
never by database id. Problems such as "no such race" are raised as ToolError and turned
into {"error": ...} by run_tool, so the model can read the message and try again.
"""

import unicodedata
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Driver, Lap, PitStop, Race, Result

RACE_PROPERTIES = {
    "season": {"type": "integer", "description": "The season (year), for example 2023."},
    "race": {
        "type": "string",
        "description": (
            "Which race of that season: a circuit name such as 'monza' or 'silverstone', "
            "part of the race name such as 'Italian' or 'Monaco', or a round number such as '14'."
        ),
    },
}
DRIVER_DESCRIPTION = (
    "A driver who took part in that race: surname, full name, driver ref or three-letter "
    "code, for example 'verstappen', 'Lewis Hamilton' or 'HAM'."
)
LIMITS = (
    "Data limits: race results exist from 2000 onward. Lap, tire and pit stop data exist "
    "only from 2023."
)

TOOLS = [
    {
        "name": "get_race_results",
        "description": (
            "Get the official classified results of one Formula 1 race: race name, date, "
            "circuit, season and round, then every driver in finishing order with position, "
            "position_text (e.g. 'R' for retired), driver name, three-letter code, team, grid "
            "slot, status (e.g. 'Finished', '+1 Lap', 'Engine') and points. Use it for "
            "questions about who won, podiums, grid positions, retirements and points. "
            "Example: season 2023, race 'monza'. " + LIMITS
        ),
        "input_schema": {
            "type": "object",
            "properties": RACE_PROPERTIES,
            "required": ["season", "race"],
        },
    },
    {
        "name": "compare_drivers",
        "description": (
            "Compare two drivers in one race. For each driver it returns finishing position, "
            "position_text and status, laps completed, average lap time (seconds) over clean "
            "laps, fastest clean lap (seconds) and number of pit stops. Clean laps have a "
            "recorded time and are not pit out laps or deleted laps. Example: season 2023, "
            "race 'monza', driver_a 'verstappen', driver_b 'perez'. Before 2023 there is no "
            "lap data, so only the results part is returned, with a note saying so. Pit stop "
            "counts are missing before the 2023 Spanish GP. " + LIMITS
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **RACE_PROPERTIES,
                "driver_a": {"type": "string", "description": DRIVER_DESCRIPTION},
                "driver_b": {"type": "string", "description": DRIVER_DESCRIPTION},
            },
            "required": ["season", "race", "driver_a", "driver_b"],
        },
    },
    {
        "name": "get_pit_strategy",
        "description": (
            "Get one driver's tire and pit stop strategy in a race. It returns the starting "
            "tire, the stints (stint number, tire type, first lap, last lap, tire age in laps "
            "at the stint's first lap) and the pit stops (lap, lane_seconds for the time "
            "spent in the pit lane, stationary_seconds for the time the car stood still). "
            "Example: season 2023, race 'monza', driver 'hamilton'. Pit stops are missing "
            "before the 2023 Spanish GP, and stationary_seconds is only filled from the 2024 "
            "US GP onward (otherwise null). Races before 2023 have no stint data. " + LIMITS
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **RACE_PROPERTIES,
                "driver": {"type": "string", "description": DRIVER_DESCRIPTION},
            },
            "required": ["season", "race", "driver"],
        },
    },
]


class ToolError(Exception):
    """The request could not be answered, and the message says how to fix it."""


def _number(value: Decimal | None) -> float | None:
    return None if value is None else round(float(value), 3)


def _plain(text: str) -> str:
    """Lowercase and drop accents, so 'Sao Paulo' matches 'São Paulo'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _race_label(race: Race) -> str:
    return f"round {race.round}: {race.name} ({race.circuit_ref})"


def find_race(db: Session, season: int, race: str) -> Race:
    races = db.scalars(select(Race).where(Race.season == season).order_by(Race.round)).all()
    query = _plain(race.strip())
    matches = [
        r
        for r in races
        if (query.isdigit() and r.round == int(query))
        or query == r.circuit_ref.lower()
        or (query and query in _plain(r.name))
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        listing = "; ".join(_race_label(r) for r in races) or "no races loaded for that season"
        raise ToolError(f"No race matching '{race}' in {season}. Races that season: {listing}")
    listing = "; ".join(_race_label(r) for r in matches)
    raise ToolError(
        f"'{race}' matches more than one race in {season}: {listing}. Use a round number."
    )


def find_driver(db: Session, race: Race, driver: str) -> Driver:
    entrants = db.scalars(
        select(Driver)
        .join(Result, Result.driver_id == Driver.id)
        .where(Result.race_id == race.id)
        .order_by(Result.position)
    ).all()
    query = _plain(driver.strip())
    matches = [
        d
        for d in entrants
        if query
        and (
            query == d.driver_ref.lower()
            or query == (d.code or "").lower()
            or query in _plain(d.full_name)
        )
    ]
    if len(matches) == 1:
        return matches[0]
    listing = ", ".join(f"{d.full_name} ({d.code})" for d in entrants)
    problem = "No driver" if not matches else "More than one driver"
    raise ToolError(
        f"{problem} matching '{driver}' in the {race.season} {race.name}. Drivers in that race: {listing}"
    )


def _race_info(race: Race) -> dict:
    return {
        "name": race.name,
        "date": race.date.isoformat(),
        "circuit_ref": race.circuit_ref,
        "season": race.season,
        "round": race.round,
    }


def _has_laps(db: Session, race: Race) -> bool:
    return db.scalar(select(func.count(Lap.id)).where(Lap.race_id == race.id)) > 0


def get_race_results(db: Session, season: int, race: str) -> dict:
    race_row = find_race(db, season, race)
    rows = db.execute(
        select(
            Result.position,
            Result.position_text,
            Driver.full_name,
            Driver.code,
            Result.team,
            Result.grid,
            Result.status,
            Result.points,
        )
        .join(Driver, Driver.id == Result.driver_id)
        .where(Result.race_id == race_row.id)
        .order_by(Result.position)
    ).all()
    results = [
        {
            "position": position,
            "position_text": position_text,
            "driver": name,
            "code": code,
            "team": team,
            "grid": grid,
            "status": status,
            "points": float(points),
        }
        for position, position_text, name, code, team, grid, status, points in rows
    ]
    return {"race": _race_info(race_row), "results": results}


def compare_drivers(db: Session, season: int, race: str, driver_a: str, driver_b: str) -> dict:
    race_row = find_race(db, season, race)
    drivers = [find_driver(db, race_row, driver_a), find_driver(db, race_row, driver_b)]
    has_laps = _has_laps(db, race_row)

    comparison = []
    for driver in drivers:
        result = db.scalars(
            select(Result).where(Result.race_id == race_row.id, Result.driver_id == driver.id)
        ).one()
        entry = {
            "driver": driver.full_name,
            "position": result.position,
            "position_text": result.position_text,
            "status": result.status,
        }
        if has_laps:
            laps_completed, average, fastest = db.execute(
                select(
                    func.count(Lap.id),
                    func.avg(Lap.lap_time_seconds).filter(
                        Lap.is_pit_out_lap.is_(False), Lap.is_deleted.is_(False)
                    ),
                    func.min(Lap.lap_time_seconds).filter(
                        Lap.is_pit_out_lap.is_(False), Lap.is_deleted.is_(False)
                    ),
                ).where(Lap.race_id == race_row.id, Lap.driver_id == driver.id)
            ).one()
            entry["laps_completed"] = laps_completed
            entry["average_clean_lap_seconds"] = _number(average)
            entry["fastest_clean_lap_seconds"] = _number(fastest)
            entry["pit_stops"] = db.scalar(
                select(func.count(PitStop.id)).where(
                    PitStop.race_id == race_row.id, PitStop.driver_id == driver.id
                )
            )
        comparison.append(entry)

    output = {"race": _race_info(race_row), "drivers": comparison}
    if not has_laps:
        output["note"] = "Lap data is not available for this race (laps start in 2023)."
    return output


def get_pit_strategy(db: Session, season: int, race: str, driver: str) -> dict:
    race_row = find_race(db, season, race)
    driver_row = find_driver(db, race_row, driver)
    output = {"race": _race_info(race_row), "driver": driver_row.full_name}
    if not _has_laps(db, race_row):
        output["note"] = "Lap and pit stop data is not available for this race (starts in 2023)."
        return output

    stints = db.execute(
        select(
            Lap.stint_number,
            func.min(Lap.tire_type),
            func.min(Lap.lap_number),
            func.max(Lap.lap_number),
            func.min(Lap.tire_age),
        )
        .where(
            Lap.race_id == race_row.id,
            Lap.driver_id == driver_row.id,
            Lap.stint_number.is_not(None),
        )
        .group_by(Lap.stint_number)
        .order_by(Lap.stint_number)
    ).all()
    pit_stops = db.scalars(
        select(PitStop)
        .where(PitStop.race_id == race_row.id, PitStop.driver_id == driver_row.id)
        .order_by(PitStop.lap_number)
    ).all()

    output["starting_tire"] = stints[0][1] if stints else None
    output["stints"] = [
        {
            "stint": number,
            "tire_type": tire,
            "first_lap": first,
            "last_lap": last,
            "tire_age_at_first_lap": age,
        }
        for number, tire, first, last, age in stints
    ]
    output["pit_stops"] = [
        {
            "lap": p.lap_number,
            "lane_seconds": _number(p.lane_seconds),
            "stationary_seconds": _number(p.stationary_seconds),
        }
        for p in pit_stops
    ]
    return output


_FUNCTIONS = {
    "get_race_results": get_race_results,
    "compare_drivers": compare_drivers,
    "get_pit_strategy": get_pit_strategy,
}


def run_tool(db: Session, name: str, tool_input: dict) -> dict:
    """Run one tool and return a JSON-serialisable dict. Never raises for bad requests."""
    function = _FUNCTIONS.get(name)
    if function is None:
        return {"error": f"Unknown tool '{name}'. Available tools: {', '.join(_FUNCTIONS)}"}
    try:
        return function(db, **tool_input)
    except ToolError as error:
        return {"error": str(error)}
    except TypeError as error:
        return {"error": f"Invalid input for {name}: {error}"}
