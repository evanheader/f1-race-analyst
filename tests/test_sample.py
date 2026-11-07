"""Tests for exporting one race to JSON and loading it back into an empty database."""

import json
import sys
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select

from app.models import Base, Driver, Lap, PitStop, Race, Result, SprintResult
from scripts import export_sample, load_sample
from tests.test_loader import rows


@pytest.fixture
def seeded(db, connection, make_race, make_driver, make_result, make_lap, make_pit_stop):
    """A race with two drivers, results, a sprint result, laps and a pit stop."""
    race = make_race(2025, 12, name="British Grand Prix", openf1_session_key=9558)
    other = make_race(2025, 1)
    nor = make_driver("norris", "NOR", "Lando Norris")
    pia = make_driver("piastri", "PIA", "Oscar Piastri")
    make_result(race, nor, driver_number=4, team="McLaren", grid=3, position=1, points=25)
    make_result(race, pia, driver_number=81, team="McLaren", grid=1, position=2, points="18.00")
    make_result(other, nor, position=5)
    connection.execute(
        SprintResult.__table__.insert().values(
            race_id=race.id,
            driver_id=nor.id,
            driver_number=4,
            team="McLaren",
            grid=1,
            position=1,
            position_text="1",
            status="Finished",
            points=Decimal(8),
        )
    )
    make_lap(race, nor, 1, "95.123", tire_type="MEDIUM", tire_age=0, stint_number=1, position=3)
    make_lap(race, nor, 2, None, is_pit_out_lap=True, is_deleted=True)
    make_lap(race, pia, 1, "94.500", tire_type="HARD", tire_age=2, stint_number=1, position=1)
    make_pit_stop(race, nor, 20, "22.500", "2.400")
    make_pit_stop(race, pia, 21, "23.100")
    return race


def snapshot(connection):
    """Every row in every table, without ids, so two databases can be compared."""
    result = {}
    for model in (Race, Driver, Result, SprintResult, Lap, PitStop):
        table = model.__table__
        keep = [c for c in table.c if c.name not in ("id", "race_id", "driver_id")]
        result[table.name] = sorted(
            tuple(row[c.name] for c in keep) for row in rows(connection, model)
        )
    return result


def test_export_contains_only_the_requested_race_keyed_by_driver_ref(connection, seeded):
    data = export_sample.export_race(connection, 2025, 12)

    assert data["race"]["name"] == "British Grand Prix"
    assert data["race"]["openf1_session_key"] == 9558
    assert [d["driver_ref"] for d in data["drivers"]] == ["norris", "piastri"]
    assert [(r["driver_ref"], r["position"]) for r in data["results"]] == [
        ("norris", 1),
        ("piastri", 2),
    ]
    assert [(r["driver_ref"], r["lap_number"]) for r in data["laps"]] == [
        ("norris", 1),
        ("norris", 2),
        ("piastri", 1),
    ]
    assert [(r["driver_ref"], r["lap_number"]) for r in data["pit_stops"]] == [
        ("norris", 20),
        ("piastri", 21),
    ]
    assert len(data["sprint_results"]) == 1
    for name in ("results", "sprint_results", "laps", "pit_stops"):
        for row in data[name]:
            assert not {"id", "race_id", "driver_id"} & row.keys()


def test_export_orders_rows_so_the_file_is_stable(connection, seeded):
    first = export_sample.export_race(connection, 2025, 12)
    second = export_sample.export_race(connection, 2025, 12)

    assert json.dumps(first, default=export_sample.jsonable) == json.dumps(
        second, default=export_sample.jsonable
    )


def test_export_stops_when_the_race_is_not_loaded(connection):
    with pytest.raises(SystemExit, match="season 2025 round 12"):
        export_sample.export_race(connection, 2025, 12)


def test_round_trip_through_json_into_an_empty_database(connection, seeded):
    other_race_id = connection.execute(
        select(Race.id).where(Race.season == 2025, Race.round == 1)
    ).scalar_one()
    data = export_sample.export_race(connection, 2025, 12)
    as_file = json.loads(json.dumps(data, default=export_sample.jsonable))
    expected = snapshot(connection)

    for model in (PitStop, Lap, SprintResult, Result, Driver, Race):
        connection.execute(delete(model))
    load_sample.load_sample(connection, as_file)

    got = snapshot(connection)
    assert got["races"] == [r for r in expected["races"] if r[1] == 12]
    for table in ("drivers", "laps", "pit_stops", "sprint_results"):
        assert got[table] == expected[table]
    # The other race's result was deleted above and is not part of the sample.
    assert len(got["results"]) == 2
    assert other_race_id not in {r.race_id for r in rows(connection, Result)}


def test_load_gives_the_api_what_it_needs(client, connection, seeded):
    data = export_sample.export_race(connection, 2025, 12)
    for model in (PitStop, Lap, SprintResult, Result, Driver, Race):
        connection.execute(delete(model))
    load_sample.load_sample(
        connection, json.loads(json.dumps(data, default=export_sample.jsonable))
    )

    race = client.get("/races").json()[0]
    assert race["name"] == "British Grand Prix"
    results = client.get(f"/races/{race['id']}/results").json()
    assert [r["position"] for r in results] == [1, 2]
    assert len(client.get(f"/races/{race['id']}/pit-stops").json()) == 2


def test_load_is_safe_to_run_twice(connection, seeded):
    data = json.loads(
        json.dumps(export_sample.export_race(connection, 2025, 12), default=export_sample.jsonable)
    )

    load_sample.load_sample(connection, data)
    load_sample.load_sample(connection, data)

    for model, count in ((Race, 2), (Driver, 2), (Lap, 3), (PitStop, 2)):
        assert connection.execute(select(func.count()).select_from(model)).scalar_one() == count


def test_load_updates_rows_that_changed(connection, seeded):
    data = json.loads(
        json.dumps(export_sample.export_race(connection, 2025, 12), default=export_sample.jsonable)
    )
    data["results"][0]["points"] = "26.00"

    load_sample.load_sample(connection, data)

    points = connection.execute(
        select(Result.points)
        .join(Driver, Driver.id == Result.driver_id)
        .where(Driver.driver_ref == "norris", Result.position == 1)
    ).scalar_one()
    assert points == Decimal("26.00")


def test_load_sample_main_reports_a_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["load_sample", "--file", str(tmp_path / "nope.json")])

    with pytest.raises(SystemExit, match="not found"):
        load_sample.main()


def test_tables_in_the_sample_match_the_models():
    assert set(export_sample.RACE_TABLES) == set(load_sample.RACE_TABLES)
    for name in export_sample.RACE_TABLES:
        assert name in Base.metadata.tables
