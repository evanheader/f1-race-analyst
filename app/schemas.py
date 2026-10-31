"""The exact shape of every answer the API gives.

Numbers that the database stores as NUMERIC are declared as float so they appear in
the JSON as numbers (26.0) instead of text ("26.000").
"""

import datetime

from pydantic import BaseModel


class RaceOut(BaseModel):
    id: int
    season: int
    round: int
    name: str
    date: datetime.date
    circuit_ref: str
    openf1_session_key: int | None


class ResultOut(BaseModel):
    driver_id: int
    driver_code: str | None
    driver_name: str
    driver_number: int
    team: str
    grid: int
    position: int
    position_text: str
    status: str
    points: float


class LapOut(BaseModel):
    driver_id: int
    lap_number: int
    lap_time_seconds: float | None
    tire_type: str | None
    tire_age: int | None
    stint_number: int | None
    position: int | None
    is_pit_out_lap: bool
    is_deleted: bool


class PitStopOut(BaseModel):
    driver_id: int
    lap_number: int
    lane_seconds: float
    stationary_seconds: float | None


class DriverStatsOut(BaseModel):
    driver_id: int
    driver_ref: str
    code: str | None
    full_name: str
    races: int
    wins: int
    points: float
    # Mean of clean laps only: laps with a time, not pit out laps, not deleted laps.
    # Null when the driver has no lap data (OpenF1 starts in 2023).
    average_lap_time_seconds: float | None
