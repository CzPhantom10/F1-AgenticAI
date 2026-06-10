"""Schemas used by system endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Standard application health payload."""

    status: str
    service: str
    version: str
    environment: str


class DatabaseHealthResponse(BaseModel):
    """Database health payload."""

    status: str
    database: str
    detail: str


class LatestSeasonResponse(BaseModel):
    """Latest season available in the database."""

    season: int


class SeasonsListResponse(BaseModel):
    """All distinct seasons available in the database."""

    seasons: list[int]