"""Pydantic schemas for memory (insights) endpoints."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MemoryRebuildResponse(BaseModel):
    """Result of memory agent rebuild execution."""

    success: bool
    drivers_processed: int
    constructors_processed: int
    circuits_processed: int
    errors: list[str]


class DriverInsightRead(BaseModel):
    """Pydantic model representing DriverInsight."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    driver_id: int
    total_races: int
    total_wins: int
    total_podiums: int
    total_points: float
    avg_finish_position: float | None
    avg_qualifying_position: float | None
    recent_form_json: str
    season_breakdown_json: str
    rebuilt_at: datetime


class ConstructorInsightRead(BaseModel):
    """Pydantic model representing ConstructorInsight."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    constructor_id: int
    total_races: int
    total_wins: int
    total_podiums: int
    total_points: float
    avg_points_per_race: float | None
    recent_form_json: str
    season_breakdown_json: str
    rebuilt_at: datetime


class CircuitInsightRead(BaseModel):
    """Pydantic model representing CircuitInsight."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    circuit_id: int
    historical_winners_json: str
    best_drivers_json: str
    best_constructors_json: str
    rebuilt_at: datetime
