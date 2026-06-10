"""Pydantic schemas for race, driver, constructor, and result endpoints."""

from __future__ import annotations

from datetime import date
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


T = TypeVar("T")


class PaginationMetadata(BaseModel):
    """Pagination metadata included with list responses."""

    limit: int
    offset: int
    total: int


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response container."""

    items: list[T]
    pagination: PaginationMetadata


class CircuitRead(BaseModel):
    """Circuit payload used in race responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str
    location: str


class RaceRead(BaseModel):
    """Race payload returned by race endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    season: int
    round_number: int
    race_name: str
    race_date: date
    circuit: CircuitRead


class DriverRead(BaseModel):
    """Driver payload returned by driver endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    driver_code: str
    first_name: str
    last_name: str
    nationality: str


class DriverRecentResultRead(BaseModel):
    """A single race result entry shown on the driver detail page."""

    race_id: int
    season: int
    round_number: int
    race_name: str
    race_date: date
    circuit_name: str
    circuit_country: str
    constructor_name: str
    grid_position: int | None
    finish_position: int | None
    points: float | None
    status: str


class DriverDetailRead(BaseModel):
    """Full driver detail payload: bio, career stats, and recent results."""

    driver: DriverRead
    # career-wide aggregates
    total_races: int
    total_wins: int
    total_podiums: int
    total_points: float
    avg_finish_position: float | None
    # last N race results ordered most-recent first
    recent_results: list[DriverRecentResultRead]


class ConstructorRead(BaseModel):
    """Constructor payload returned by constructor endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    nationality: str


class RaceResultRead(BaseModel):
    """Race result payload returned by latest results endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    driver: DriverRead
    constructor: ConstructorRead
    grid_position: int | None
    finish_position: int | None
    points: float | None
    status: str


class QualifyingResultRead(BaseModel):
    """Qualifying result payload returned by latest qualifying endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    driver: DriverRead
    constructor: ConstructorRead
    qualifying_position: int | None
    q1_time: float | None
    q2_time: float | None
    q3_time: float | None


class LatestRaceResultsResponse(BaseModel):
    """Latest race and its results."""

    race: RaceRead
    results: list[RaceResultRead]


class LatestQualifyingResultsResponse(BaseModel):
    """Latest race and its qualifying results."""

    race: RaceRead
    results: list[QualifyingResultRead]


class DriverStandingRead(BaseModel):
    """Single driver standings row."""

    model_config = ConfigDict(from_attributes=True)

    position: int
    points: float
    wins: int
    podiums: int
    races: int
    driver: DriverRead


class ConstructorStandingRead(BaseModel):
    """Single constructor standings row."""

    model_config = ConfigDict(from_attributes=True)

    position: int
    points: float
    wins: int
    podiums: int
    races: int
    constructor: ConstructorRead


class UpcomingRaceRead(BaseModel):
    """Upcoming race payload from the schedule cache."""

    season: int
    round_number: int
    race_name: str
    race_date: date
    circuit: CircuitRead
    days_until: int
