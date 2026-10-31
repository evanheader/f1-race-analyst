import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Race(Base):
    __tablename__ = "races"
    __table_args__ = (UniqueConstraint("season", "round"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int]
    round: Mapped[int]
    name: Mapped[str]
    date: Mapped[datetime.date]
    circuit_ref: Mapped[str]
    openf1_session_key: Mapped[int | None] = mapped_column(unique=True)


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_ref: Mapped[str] = mapped_column(unique=True)
    code: Mapped[str | None]
    full_name: Mapped[str]


class Result(Base):
    __tablename__ = "results"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id"),
        Index("ix_results_driver_id", "driver_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    driver_number: Mapped[int]
    team: Mapped[str]
    grid: Mapped[int]
    position: Mapped[int]
    position_text: Mapped[str]
    status: Mapped[str]
    points: Mapped[Decimal] = mapped_column(Numeric(5, 2))


class SprintResult(Base):
    __tablename__ = "sprint_results"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id"),
        Index("ix_sprint_results_driver_id", "driver_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    driver_number: Mapped[int]
    team: Mapped[str]
    grid: Mapped[int]
    position: Mapped[int]
    position_text: Mapped[str]
    status: Mapped[str]
    points: Mapped[Decimal] = mapped_column(Numeric(5, 2))


class Lap(Base):
    __tablename__ = "laps"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id", "lap_number"),
        Index("ix_laps_driver_id", "driver_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    lap_number: Mapped[int]
    lap_time_seconds: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    tire_type: Mapped[str | None]
    tire_age: Mapped[int | None]
    stint_number: Mapped[int | None]
    position: Mapped[int | None]
    is_pit_out_lap: Mapped[bool]
    is_deleted: Mapped[bool]


class PitStop(Base):
    __tablename__ = "pit_stops"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id", "lap_number"),
        Index("ix_pit_stops_driver_id", "driver_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    lap_number: Mapped[int]
    lane_seconds: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    stationary_seconds: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
