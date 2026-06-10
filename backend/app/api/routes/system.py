"""System and health-check endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db, ping_database
from app.models import Race
from app.schemas.system import DatabaseHealthResponse, HealthResponse, LatestSeasonResponse, SeasonsListResponse


settings = get_settings()
router = APIRouter(tags=["System"])
seasons_router = APIRouter(prefix="/seasons", tags=["Seasons"])


@router.get("/", response_model=HealthResponse)
def root() -> HealthResponse:
    """Return a simple application status response."""

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return the API health status."""

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/health/db", response_model=DatabaseHealthResponse)
def database_health(db: Session = Depends(get_db)) -> DatabaseHealthResponse:
    """Verify SQLite is reachable and able to execute a trivial query."""

    try:
        db.execute(text("SELECT 1"))
        ping_database()
    except Exception as exc:  # pragma: no cover - runtime connectivity only
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc

    return DatabaseHealthResponse(
        status="ok",
        database="sqlite",
        detail="Database connection successful",
    )


@seasons_router.get("/latest", response_model=LatestSeasonResponse)
def latest_season(db: Session = Depends(get_db)) -> LatestSeasonResponse:
    """Return the most recent season year present in the races table."""

    season = db.scalar(select(func.max(Race.season)))
    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No seasons found in the database",
        )
    return LatestSeasonResponse(season=int(season))


@seasons_router.get("", response_model=SeasonsListResponse)
def list_seasons(db: Session = Depends(get_db)) -> SeasonsListResponse:
    """Return all distinct season years present in the races table, newest first."""

    rows = db.execute(
        select(Race.season).distinct().order_by(Race.season.desc())
    ).scalars().all()
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No seasons found in the database",
        )
    return SeasonsListResponse(seasons=[int(y) for y in rows])