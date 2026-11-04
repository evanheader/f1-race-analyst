"""Shared fixtures. Every test runs against TEST_DATABASE_URL, never DATABASE_URL.

The tables are created once per run. Each test then works inside a transaction that is
rolled back when it ends, so tests start empty and never see each other's rows.
"""

import datetime
import os
from decimal import Decimal

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

load_dotenv()
TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]
if not make_url(TEST_DATABASE_URL).database.endswith("_test"):
    raise RuntimeError(f"TEST_DATABASE_URL must name a *_test database, got {TEST_DATABASE_URL}")
# app.database builds its engine on import. Point it at the test database too, so
# nothing in a test can reach real data even by accident.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Base, Driver, Lap, PitStop, Race, Result, SprintResult


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def connection(engine):
    with engine.connect() as conn:
        transaction = conn.begin()
        yield conn
        transaction.rollback()


@pytest.fixture
def db(connection):
    # Commits inside the code under test become savepoints, so the rollback still wins.
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        yield session


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_race(db):
    def make(season=2024, round=1, **fields):
        race = Race(
            season=season,
            round=round,
            name=fields.pop("name", f"Race {season}-{round}"),
            date=fields.pop("date", datetime.date(season, 3, round)),
            circuit_ref=fields.pop("circuit_ref", "bahrain"),
            **fields,
        )
        db.add(race)
        db.flush()
        return race

    return make


@pytest.fixture
def make_driver(db):
    def make(driver_ref="max_verstappen", code="VER", full_name="Max Verstappen"):
        driver = Driver(driver_ref=driver_ref, code=code, full_name=full_name)
        db.add(driver)
        db.flush()
        return driver

    return make


def _result_fields(race, driver, fields):
    position = fields.pop("position", 1)
    return dict(
        race_id=race.id,
        driver_id=driver.id,
        driver_number=fields.pop("driver_number", 1),
        team=fields.pop("team", "Red Bull"),
        grid=fields.pop("grid", 1),
        position=position,
        position_text=fields.pop("position_text", str(position)),
        status=fields.pop("status", "Finished"),
        points=Decimal(str(fields.pop("points", 0))),
        **fields,
    )


@pytest.fixture
def make_result(db):
    def make(race, driver, **fields):
        result = Result(**_result_fields(race, driver, fields))
        db.add(result)
        db.flush()
        return result

    return make


@pytest.fixture
def make_sprint_result(db):
    def make(race, driver, **fields):
        result = SprintResult(**_result_fields(race, driver, fields))
        db.add(result)
        db.flush()
        return result

    return make


@pytest.fixture
def make_lap(db):
    def make(race, driver, lap_number, lap_time_seconds="90.000", **fields):
        lap = Lap(
            race_id=race.id,
            driver_id=driver.id,
            lap_number=lap_number,
            lap_time_seconds=None if lap_time_seconds is None else Decimal(lap_time_seconds),
            is_pit_out_lap=fields.pop("is_pit_out_lap", False),
            is_deleted=fields.pop("is_deleted", False),
            **fields,
        )
        db.add(lap)
        db.flush()
        return lap

    return make


@pytest.fixture
def make_pit_stop(db):
    def make(race, driver, lap_number, lane_seconds="22.500", stationary_seconds=None):
        stop = PitStop(
            race_id=race.id,
            driver_id=driver.id,
            lap_number=lap_number,
            lane_seconds=Decimal(lane_seconds),
            stationary_seconds=None if stationary_seconds is None else Decimal(stationary_seconds),
        )
        db.add(stop)
        db.flush()
        return stop

    return make
