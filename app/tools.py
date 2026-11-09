"""The tools Claude can call to read race data. All of them only run SELECTs.

Every tool identifies things the way a person would (season + race name, driver name),
never by database id. Problems such as "no such race" are raised as ToolError and turned
into {"error": ...} by run_tool, so the model can read the message and try again.
"""

import unicodedata
from decimal import Decimal

from sqlalchemy import case, func, literal_column, select
from sqlalchemy.orm import Session

from app.models import Driver, Lap, PitStop, Race, Result, SprintResult

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
            "questions about who won, podiums, grid positions, retirements and points. The "
            "output also lists the season's races (season_races), so you can spot other "
            "races that may match the question. "
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
    {
        "name": "get_season_summary",
        "description": (
            "Get one driver's or one team's totals over a whole Formula 1 season: races "
            "(starts, withdrawals not counted), wins, podiums, race_points, sprint_points, "
            "total_points and retirements, plus a per-race list in round order (round, race "
            "name, position_text, points, and the team for a driver or the driver for a team). "
            "Use it for season-wide questions such as how many races a driver won, how many "
            "podiums a team got, or how many points or retirements a driver or team had in a "
            "season. Give the season and exactly one of driver or team. For a team the totals "
            "count each car's result, so a 1-2 finish is 1 win and 2 podiums. Sprint points "
            "are separate: they are in sprint_points and total_points, not in race_points, "
            "wins or podiums. For a single race use get_race_results instead. Example: "
            "season 2023, driver 'verstappen', or season 2024, team 'mclaren'. Season data "
            "starts in 2000."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "season": RACE_PROPERTIES["season"],
                "driver": {
                    "type": "string",
                    "description": (
                        "A driver who raced that season: surname, full name, driver ref or "
                        "three-letter code, for example 'verstappen' or 'HAM'."
                    ),
                },
                "team": {
                    "type": "string",
                    "description": "A team that raced that season, for example 'Red Bull' or 'mclaren'.",
                },
            },
            "required": ["season"],
        },
    },
    {
        "name": "get_laps",
        "description": (
            "Get lap-by-lap data for one race. Give a driver, a lap number, or both. With only "
            "a driver it returns that driver's laps in order (lap, time in seconds or null, "
            "position, tire, tire_age, pit_out, deleted) plus a summary: number of laps, "
            "fastest clean lap (lap number and time) and the lap numbers of deleted laps. "
            "Clean laps have a recorded time and are not pit out laps or deleted laps. With "
            "only a lap it returns the running order at the end of that lap: every driver "
            "with position, driver name, code, time and tire, in position order. With both it "
            "returns that driver's single lap. Use it for lap-by-lap questions: who led on "
            "lap N, lap times, which lap was fastest, deleted laps (for example for track "
            "limits), tire age on a lap, or how a driver's pace changed. Example: season "
            "2024, race 'interlagos', lap 35. Positions are derived from timing data and can "
            "be slightly off around pit stops and on a driver's final lap, so for final "
            "positions use get_race_results. Lap data exists only from 2023; earlier races "
            "return a note instead. " + LIMITS
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **RACE_PROPERTIES,
                "driver": {"type": "string", "description": DRIVER_DESCRIPTION},
                "lap": {"type": "integer", "description": "A lap number, starting at 1."},
            },
            "required": ["season", "race"],
        },
    },
    {
        "name": "get_championship_progression",
        "description": (
            "Get one driver's drivers' championship standing after every round of a season. "
            "For each round that has results, in round order, it returns the round, race "
            "name, date, the driver's points from that round (race plus sprint), the "
            "driver's total_points so far, their championship position after the round, and "
            "the leader's name and points plus the gap_to_leader (0 when the driver leads; "
            "then gap_to_second is the lead over the next driver). Use it for questions "
            "such as when a driver took the lead, what the gap to the leader was after round "
            "N, or when the gap dropped below some number of points. A driver who missed a "
            "round scores 0 for it. Drivers level on points are ranked by wins so far, and "
            "drivers still level share a position. Example: season 2024, driver 'norris'. "
            "Season data starts in 2000."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "season": RACE_PROPERTIES["season"],
                "driver": {
                    "type": "string",
                    "description": (
                        "A driver who raced that season: surname, full name, driver ref or "
                        "three-letter code, for example 'verstappen' or 'HAM'."
                    ),
                },
            },
            "required": ["season", "driver"],
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
        or query == _plain(r.name)
    ] or [r for r in races if query and query in _plain(r.name)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        listing = "; ".join(_race_label(r) for r in races) or "no races loaded for that season"
        raise ToolError(f"No race matching '{race}' in {season}. Races that season: {listing}")
    listing = "; ".join(_race_label(r) for r in matches)
    raise ToolError(
        f"'{race}' matches more than one race in {season}: {listing}. Use a round number."
    )


def _matching_drivers(drivers: list[Driver], text: str) -> list[Driver]:
    query = _plain(text.strip())
    exact = [
        d
        for d in drivers
        if query
        and (
            query == d.driver_ref.lower()
            or query == (d.code or "").lower()
            or query == _plain(d.full_name)
        )
    ]
    return exact or [d for d in drivers if query and query in _plain(d.full_name)]


def find_driver(db: Session, race: Race, driver: str) -> Driver:
    entrants = db.scalars(
        select(Driver)
        .join(Result, Result.driver_id == Driver.id)
        .where(Result.race_id == race.id)
        .order_by(Result.position)
    ).all()
    matches = _matching_drivers(entrants, driver)
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
    season_races = db.scalars(select(Race).where(Race.season == season).order_by(Race.round)).all()
    return {
        "race": _race_info(race_row),
        "season_races": [_race_label(r) for r in season_races],
        "results": results,
    }


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


def find_season_driver(db: Session, season: int, driver: str) -> Driver:
    entrants = db.scalars(
        select(Driver)
        .join(Result, Result.driver_id == Driver.id)
        .join(Race, Race.id == Result.race_id)
        .where(Race.season == season)
        .distinct()
        .order_by(Driver.full_name)
    ).all()
    matches = _matching_drivers(entrants, driver)
    if len(matches) == 1:
        return matches[0]
    listing = ", ".join(f"{d.full_name} ({d.code})" for d in entrants)
    problem = "No driver" if not matches else "More than one driver"
    raise ToolError(
        f"{problem} matching '{driver}' in {season}. Drivers that season: "
        f"{listing or 'no results loaded for that season'}"
    )


def _season_filter(db: Session, season: int, driver: str | None, team: str | None):
    """Return who the summary is about, plus conditions for results and sprint_results."""
    if (driver is None) == (team is None):
        raise ToolError("Give exactly one of driver or team.")
    if driver is not None:
        found = find_season_driver(db, season, driver)
        return found.full_name, Result.driver_id == found.id, SprintResult.driver_id == found.id
    teams = db.scalars(
        select(Result.team)
        .join(Race, Race.id == Result.race_id)
        .where(Race.season == season)
        .distinct()
        .order_by(Result.team)
    ).all()
    query = _plain(team.strip())
    matches = [t for t in teams if query and query == _plain(t)] or [
        t for t in teams if query and query in _plain(t)
    ]
    if len(matches) == 1:
        return matches[0], Result.team == matches[0], SprintResult.team == matches[0]
    problem = "No team" if not matches else "More than one team"
    raise ToolError(
        f"{problem} matching '{team}' in {season}. Teams that season: "
        f"{', '.join(teams) or 'no results loaded for that season'}"
    )


def get_season_summary(
    db: Session, season: int, driver: str | None = None, team: str | None = None
) -> dict:
    name, in_results, in_sprints = _season_filter(db, season, driver, team)
    position = Result.position_text
    races, wins, podiums, race_points, retirements = db.execute(
        select(
            func.count(Result.id).filter(position != "W"),
            func.count(Result.id).filter(position == "1"),
            func.count(Result.id).filter(position.in_(["1", "2", "3"])),
            func.coalesce(func.sum(Result.points), 0),
            func.count(Result.id).filter(position == "R"),
        )
        .join(Race, Race.id == Result.race_id)
        .where(Race.season == season, in_results)
    ).one()
    sprint_points = db.scalar(
        select(func.coalesce(func.sum(SprintResult.points), 0))
        .join(Race, Race.id == SprintResult.race_id)
        .where(Race.season == season, in_sprints)
    )
    per_race = db.execute(
        select(Race.round, Race.name, position, Result.points, Driver.full_name, Result.team)
        .join(Race, Race.id == Result.race_id)
        .join(Driver, Driver.id == Result.driver_id)
        .where(Race.season == season, in_results)
        .order_by(Race.round, Result.position)
    ).all()
    by_team = driver is None
    return {
        "season": season,
        "driver" if driver is not None else "team": name,
        "races": races,
        "wins": wins,
        "podiums": podiums,
        "race_points": _number(race_points),
        "sprint_points": _number(sprint_points),
        "total_points": _number(race_points + sprint_points),
        "retirements": retirements,
        "results": [
            {
                "round": round_,
                "race": race_name,
                "driver" if by_team else "team": driver_name if by_team else team_name,
                "position_text": position_text,
                "points": _number(points),
            }
            for round_, race_name, position_text, points, driver_name, team_name in per_race
        ],
    }


def _lap_entry(lap: Lap) -> dict:
    return {
        "lap": lap.lap_number,
        "time": _number(lap.lap_time_seconds),
        "pos": lap.position,
        "tire": lap.tire_type,
        "tire_age": lap.tire_age,
        "pit_out": lap.is_pit_out_lap,
        "deleted": lap.is_deleted,
    }


def get_laps(
    db: Session, season: int, race: str, driver: str | None = None, lap: int | None = None
) -> dict:
    if driver is None and lap is None:
        raise ToolError("Give a driver, a lap number, or both.")
    race_row = find_race(db, season, race)
    driver_row = None if driver is None else find_driver(db, race_row, driver)
    output = {"race": _race_info(race_row)}
    if not _has_laps(db, race_row):
        output["note"] = "Lap data is not available for this race (starts in 2023)."
        return output

    race_laps = Lap.race_id == race_row.id
    if lap is not None:
        total = db.scalar(select(func.max(Lap.lap_number)).where(race_laps))
        if not 1 <= lap <= total:
            raise ToolError(f"Lap {lap} does not exist: the race had {total} laps.")

    if driver_row is None:
        rows = db.execute(
            select(Lap, Driver)
            .join(Driver, Driver.id == Lap.driver_id)
            .where(race_laps, Lap.lap_number == lap)
            .order_by(Lap.position.nulls_last(), Driver.full_name)
        ).all()
        output["lap"] = lap
        output["running_order"] = [
            {
                "pos": row.position,
                "driver": row_driver.full_name,
                "code": row_driver.code,
                "time": _number(row.lap_time_seconds),
                "tire": row.tire_type,
            }
            for row, row_driver in rows
        ]
        return output

    conditions = [race_laps, Lap.driver_id == driver_row.id]
    if lap is not None:
        conditions.append(Lap.lap_number == lap)
    laps = db.scalars(select(Lap).where(*conditions).order_by(Lap.lap_number)).all()
    output["driver"] = driver_row.full_name
    if lap is not None:
        if not laps:
            raise ToolError(f"{driver_row.full_name} has no lap {lap} in this race.")
        output["lap"] = _lap_entry(laps[0])
        return output

    clean = [
        x
        for x in laps
        if x.lap_time_seconds is not None and not x.is_pit_out_lap and not x.is_deleted
    ]
    fastest = min(clean, key=lambda x: x.lap_time_seconds, default=None)
    output["summary"] = {
        "laps": len(laps),
        "fastest_clean_lap": (
            None
            if fastest is None
            else {"lap": fastest.lap_number, "time": _number(fastest.lap_time_seconds)}
        ),
        "deleted_laps": [x.lap_number for x in laps if x.is_deleted],
    }
    output["laps"] = [_lap_entry(x) for x in laps]
    return output


def get_championship_progression(db: Session, season: int, driver: str) -> dict:
    driver_row = find_season_driver(db, season, driver)
    races = db.scalars(
        select(Race)
        .where(Race.season == season, Race.id.in_(select(Result.race_id)))
        .order_by(Race.round)
    ).all()
    # Race and sprint points of every driver, with 1 for a race win, in one query.
    won = case((Result.position_text == "1", 1), else_=0)
    scored = (
        select(Result.race_id, Result.driver_id, Result.points, won.label("win"))
        .union_all(
            select(
                SprintResult.race_id,
                SprintResult.driver_id,
                SprintResult.points,
                literal_column("0"),
            )
        )
        .subquery()
    )
    rows = db.execute(
        select(
            scored.c.race_id,
            Driver.full_name,
            Driver.id,
            func.sum(scored.c.points),
            func.sum(scored.c.win),
        )
        .join(Driver, Driver.id == scored.c.driver_id)
        .join(Race, Race.id == scored.c.race_id)
        .where(Race.season == season)
        .group_by(scored.c.race_id, Driver.id, Driver.full_name)
    ).all()

    total, wins, names = {}, {}, {}
    progression = []
    for race in races:
        round_points = 0
        for race_id, name, driver_id, points, win in rows:
            if race_id == race.id:
                names[driver_id] = name
                total[driver_id] = total.get(driver_id, 0) + points
                wins[driver_id] = wins.get(driver_id, 0) + win
                if driver_id == driver_row.id:
                    round_points = points
        # Most points first, then most wins, then name so that the order is stable.
        standings = sorted(total, key=lambda d: (-total[d], -wins[d], names[d]))
        mine = total.get(driver_row.id, 0)
        position = 1 + sum(
            1 for d in total if (total[d], wins[d]) > (mine, wins.get(driver_row.id, 0))
        )
        entry = {
            "round": race.round,
            "race": race.name,
            "date": race.date.isoformat(),
            "points": _number(round_points),
            "total_points": _number(mine),
            "position": position,
        }
        if position == 1:
            others = [d for d in standings if d != driver_row.id]
            entry["leader"] = driver_row.full_name
            entry["leader_points"] = _number(mine)
            entry["gap_to_leader"] = 0
            if others:
                entry["gap_to_second"] = _number(mine - total[others[0]])
        else:
            leader = standings[0]
            entry["leader"] = names[leader]
            entry["leader_points"] = _number(total[leader])
            entry["gap_to_leader"] = _number(total[leader] - mine)
        progression.append(entry)
    return {"season": season, "driver": driver_row.full_name, "rounds": progression}


_FUNCTIONS = {
    "get_race_results": get_race_results,
    "compare_drivers": compare_drivers,
    "get_pit_strategy": get_pit_strategy,
    "get_season_summary": get_season_summary,
    "get_laps": get_laps,
    "get_championship_progression": get_championship_progression,
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
