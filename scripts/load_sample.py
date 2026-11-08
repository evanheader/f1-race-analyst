"""Load the bundled sample race into the database, with no internet needed.

Usage: uv run python -m scripts.load_sample [--file PATH]

The sample is one real race, written by scripts.export_sample. Safe to run again: every
write is an upsert, the same as scripts.load_data.
"""

import argparse
import json
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, select

from app.models import Driver, Lap, PitStop, Race, Result, SprintResult
from scripts.load_data import upsert

DEFAULT_FILE = Path(__file__).parent / "sample_race.json"

RACE_TABLES = {
    "results": (Result, ["race_id", "driver_id"]),
    "sprint_results": (SprintResult, ["race_id", "driver_id"]),
    "laps": (Lap, ["race_id", "driver_id", "lap_number"]),
    "pit_stops": (PitStop, ["race_id", "driver_id", "lap_number"]),
}


def load_sample(conn, data: dict) -> None:
    """Upsert the race, its drivers and everything that hangs off them."""
    race = {**data["race"], "date": date.fromisoformat(data["race"]["date"])}
    upsert(conn, Race, [race], ["season", "round"])
    race_id = conn.execute(
        select(Race.id).where(Race.season == race["season"], Race.round == race["round"])
    ).scalar_one()

    upsert(conn, Driver, data["drivers"], ["driver_ref"])
    driver_ids = dict(conn.execute(select(Driver.driver_ref, Driver.id)).all())

    for name, (model, key) in RACE_TABLES.items():
        rows = [
            {
                **{k: v for k, v in row.items() if k != "driver_ref"},
                "race_id": race_id,
                "driver_id": driver_ids[row["driver_ref"]],
            }
            for row in data.get(name, [])
        ]
        upsert(conn, model, rows, key)
        print(f"{name}: {len(rows)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"{args.file} not found. Create it with scripts.export_sample.")
    data = json.loads(args.file.read_text())

    load_dotenv()
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        load_sample(conn, data)
    print(f"Loaded {data['race']['name']} {data['race']['season']}.")


if __name__ == "__main__":
    main()
