"""Export one race from the database to a JSON file that scripts.load_sample can load.

Usage: uv run python -m scripts.export_sample [--season 2025] [--round 12] [--out PATH]

Run this after scripts.load_data has loaded the race, then commit the file it writes.
Rows are keyed by driver_ref instead of database ids, because ids differ between databases.
"""

import argparse
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, select

from app.models import Driver, Lap, PitStop, Race, Result, SprintResult

DEFAULT_OUT = Path(__file__).parent / "sample_race.json"

# Tables that hold one row per driver per race, and how to order their rows in the file.
RACE_TABLES = {
    "results": (Result, lambda r: (r["position"], r["driver_ref"])),
    "sprint_results": (SprintResult, lambda r: (r["position"], r["driver_ref"])),
    "laps": (Lap, lambda r: (r["driver_ref"], r["lap_number"])),
    "pit_stops": (PitStop, lambda r: (r["lap_number"], r["driver_ref"])),
}


def jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"cannot write {type(value).__name__} to JSON")


def export_race(conn, season: int, round: int) -> dict:
    """Everything the database holds for one race, as plain data."""
    race = (
        conn.execute(select(Race.__table__).where(Race.season == season, Race.round == round))
        .mappings()
        .one_or_none()
    )
    if race is None:
        raise SystemExit(f"No race for season {season} round {round}. Run scripts.load_data first.")

    found = {}
    for name, (model, _) in RACE_TABLES.items():
        table = model.__table__
        found[name] = (
            conn.execute(select(table).where(table.c.race_id == race["id"])).mappings().all()
        )

    driver_ids = {row["driver_id"] for rows in found.values() for row in rows}
    drivers = (
        conn.execute(select(Driver.__table__).where(Driver.id.in_(driver_ids))).mappings().all()
    )
    ref_by_id = {d["id"]: d["driver_ref"] for d in drivers}

    data = {
        "race": {k: v for k, v in race.items() if k != "id"},
        "drivers": sorted(
            ({k: v for k, v in d.items() if k != "id"} for d in drivers),
            key=lambda d: d["driver_ref"],
        ),
    }
    for name, (_, order) in RACE_TABLES.items():
        rows = [
            {
                **{k: v for k, v in row.items() if k not in ("id", "race_id", "driver_id")},
                "driver_ref": ref_by_id[row["driver_id"]],
            }
            for row in found[name]
        ]
        data[name] = sorted(rows, key=order)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--round", type=int, default=12, help="12 is the 2025 British Grand Prix")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    load_dotenv()
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        data = export_race(conn, args.season, args.round)

    args.out.write_text(json.dumps(data, default=jsonable, indent=1) + "\n")
    print(
        f"Wrote {args.out}: {data['race']['name']} {data['race']['season']}, "
        f"{len(data['drivers'])} drivers, {len(data['results'])} results, "
        f"{len(data['laps'])} laps, {len(data['pit_stops'])} pit stops"
    )


if __name__ == "__main__":
    main()
