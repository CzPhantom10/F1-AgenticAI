"""Pydantic schemas for the data-sync service and admin endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RaceImportDetail(BaseModel):
    """Result of importing a single race round."""

    season: int
    round_number: int
    race_name: str
    race_results_imported: int
    qualifying_results_imported: int
    success: bool
    error: str | None = None


class SyncResponse(BaseModel):
    """Response body returned by POST /admin/sync."""

    updated: bool = Field(description="True when at least one new race was imported.")
    new_races: int = Field(description="Number of race rounds imported in this sync run.")
    drivers_updated: bool = Field(
        description="True when at least one new driver row was created."
    )
    constructors_updated: bool = Field(
        description="True when at least one new constructor row was created."
    )
    seasons_touched: list[int] = Field(
        default_factory=list,
        description="Distinct season years that received new data.",
    )
    races: list[RaceImportDetail] = Field(
        default_factory=list,
        description="Per-race import details.",
    )
    message: str = Field(description="Human-readable summary of the sync run.")
