from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Driver, Lap, PitStop, Race, Result, SprintResult
from app.schemas import DriverStatsOut, LapOut, PitStopOut, RaceOut, ResultOut

app = FastAPI(title="F1 Race Analyst")


def get_race_or_404(db: Session, race_id: int) -> Race:
    race = db.get(Race, race_id)
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return race


@app.get("/races", response_model=list[RaceOut])
def list_races(season: int | None = None, db: Session = Depends(get_db)):
    query = select(Race).order_by(Race.season, Race.round)
    if season is not None:
        query = query.where(Race.season == season)
    return db.scalars(query).all()


@app.get("/races/{race_id}/results", response_model=list[ResultOut])
def race_results(race_id: int, db: Session = Depends(get_db)):
    get_race_or_404(db, race_id)
    rows = db.execute(
        select(
            Result.driver_id,
            Driver.code.label("driver_code"),
            Driver.full_name.label("driver_name"),
            Result.driver_number,
            Result.team,
            Result.grid,
            Result.position,
            Result.position_text,
            Result.status,
            Result.points,
        )
        .join(Driver, Driver.id == Result.driver_id)
        .where(Result.race_id == race_id)
        .order_by(Result.position)
    ).all()
    return rows


@app.get("/races/{race_id}/laps", response_model=list[LapOut])
def race_laps(race_id: int, driver_id: int | None = None, db: Session = Depends(get_db)):
    get_race_or_404(db, race_id)
    query = select(Lap).where(Lap.race_id == race_id).order_by(Lap.driver_id, Lap.lap_number)
    if driver_id is not None:
        if db.get(Driver, driver_id) is None:
            raise HTTPException(status_code=404, detail="Driver not found")
        query = query.where(Lap.driver_id == driver_id)
    return db.scalars(query).all()


@app.get("/races/{race_id}/pit-stops", response_model=list[PitStopOut])
def race_pit_stops(race_id: int, db: Session = Depends(get_db)):
    get_race_or_404(db, race_id)
    query = (
        select(PitStop)
        .where(PitStop.race_id == race_id)
        .order_by(PitStop.lap_number, PitStop.driver_id)
    )
    return db.scalars(query).all()


@app.get("/drivers/{driver_id}/stats", response_model=DriverStatsOut)
def driver_stats(driver_id: int, db: Session = Depends(get_db)):
    driver = db.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")

    races, wins, points = db.execute(
        select(
            func.count(Result.id),
            func.count(Result.id).filter(Result.position_text == "1"),
            func.coalesce(func.sum(Result.points), 0),
        ).where(Result.driver_id == driver_id)
    ).one()
    sprint_points = db.scalar(
        select(func.coalesce(func.sum(SprintResult.points), 0)).where(
            SprintResult.driver_id == driver_id
        )
    )
    average_lap = db.scalar(
        select(func.avg(Lap.lap_time_seconds)).where(
            Lap.driver_id == driver_id,
            Lap.is_pit_out_lap.is_(False),
            Lap.is_deleted.is_(False),
        )
    )
    return {
        "driver_id": driver.id,
        "driver_ref": driver.driver_ref,
        "code": driver.code,
        "full_name": driver.full_name,
        "races": races,
        "wins": wins,
        "points": points + sprint_points,
        "average_lap_time_seconds": average_lap,
    }
