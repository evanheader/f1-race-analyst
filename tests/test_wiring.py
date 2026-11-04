"""Tests for the glue code: the request database session, table creation and the loader CLI."""

from contextlib import contextmanager

import pytest
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Base, Result
from scripts import create_tables, load_data
from scripts.load_data import RetryLater
from tests.test_loader import add_driver, add_race


def test_get_db_yields_a_session_and_closes_it():
    sessions = get_db()
    session = next(sessions)
    assert isinstance(session, Session)
    session.connection()  # opens a real connection to the test database
    assert session.in_transaction()

    with pytest.raises(StopIteration):
        next(sessions)

    assert not session.in_transaction()


def test_create_tables_creates_every_table(engine):
    Base.metadata.drop_all(engine)
    assert inspect(engine).get_table_names() == []

    create_tables.main()

    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables)


def test_create_tables_is_safe_to_rerun(engine):
    create_tables.main()
    create_tables.main()

    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables)


# load_data.main


@pytest.fixture
def loader(monkeypatch, connection):
    """Run load_data.main on the test connection with the load steps replaced by recorders."""
    calls = []

    class FakeEngine:
        @contextmanager
        def begin(self):
            with connection.begin_nested():
                yield connection

        @contextmanager
        def connect(self):
            yield connection

    monkeypatch.setattr(load_data, "create_engine", lambda url: FakeEngine())
    monkeypatch.setattr(
        load_data, "load_races", lambda conn, season: calls.append(("races", season))
    )
    monkeypatch.setattr(
        load_data,
        "load_results",
        lambda conn, season, sprint=False: calls.append(
            ("sprint" if sprint else "results", season)
        ),
    )
    monkeypatch.setattr(
        load_data,
        "load_race_laps",
        lambda conn, race, drivers: calls.append(("laps", race.round, drivers)),
    )

    def run(*args):
        monkeypatch.setattr("sys.argv", ["load_data", *map(str, args)])
        load_data.main()
        return calls

    return run


def add_result(connection, race, driver_id, number):
    connection.execute(
        insert(Result).values(
            race_id=race.id,
            driver_id=driver_id,
            driver_number=number,
            team="McLaren",
            grid=1,
            position=1,
            position_text="1",
            status="Finished",
            points=25,
        )
    )


def test_main_defaults_to_2023_and_2024(loader):
    calls = loader()

    assert [c for c in calls if c[0] != "laps"] == [
        ("races", 2023),
        ("results", 2023),
        ("sprint", 2023),
        ("races", 2024),
        ("results", 2024),
        ("sprint", 2024),
    ]


def test_main_loads_laps_in_round_order_with_each_races_car_numbers(loader, connection):
    second = add_race(connection, 2024, 2, session_key=2002)
    first = add_race(connection, 2024, 1, session_key=2001)
    norris, piastri = add_driver(connection, "norris"), add_driver(connection, "piastri")
    add_result(connection, first, norris, 4)
    add_result(connection, second, norris, 1)  # a new car number the next race
    add_result(connection, second, piastri, 81)

    calls = loader(2024)

    assert [c for c in calls if c[0] == "laps"] == [
        ("laps", 1, {4: norris}),
        ("laps", 2, {1: norris, 81: piastri}),
    ]


def test_main_skips_laps_for_races_without_openf1_data(loader, connection):
    add_race(connection, 2024, 1, session_key=None)

    calls = loader(2024)

    assert [c for c in calls if c[0] == "laps"] == []


def test_main_round_option_loads_laps_for_that_round_only(loader, connection):
    for round in (1, 2, 3):
        add_race(connection, 2024, round, session_key=2000 + round)

    calls = loader(2024, "--round", 2)

    assert [c[1] for c in calls if c[0] == "laps"] == [2]


def test_main_retry_later_stops_with_a_rerun_message(loader, monkeypatch):
    def locked(conn, season):
        raise RetryLater("401 from https://api.openf1.org/v1/sessions. Try again later.")

    monkeypatch.setattr(load_data, "load_races", locked)

    with pytest.raises(SystemExit) as stopped:
        loader(2024)

    assert "Rerun later" in str(stopped.value)
    assert "401" in str(stopped.value)
