"""Resource endpoints for races, drivers, constructors, and latest results."""

from __future__ import annotations

from datetime import date

import fastf1
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.database.session import get_db
from app.models import Constructor, Driver, QualifyingResult, Race, RaceResult
from app.models.circuit import Circuit
from app.schemas.resources import (
    ConstructorRead,
    ConstructorStandingRead,
    DriverDetailRead,
    DriverRead,
    DriverRecentResultRead,
    DriverStandingRead,
    LatestQualifyingResultsResponse,
    LatestRaceResultsResponse,
    PaginatedResponse,
    PaginationMetadata,
    QualifyingResultRead,
    RaceRead,
    RaceResultRead,
    UpcomingRaceRead,
)


races_router = APIRouter(prefix="/races", tags=["Races"])
drivers_router = APIRouter(prefix="/drivers", tags=["Drivers"])
constructors_router = APIRouter(prefix="/constructors", tags=["Constructors"])
results_router = APIRouter(prefix="/results", tags=["Results"])
qualifying_router = APIRouter(prefix="/qualifying", tags=["Qualifying"])
standings_router = APIRouter(prefix="/standings", tags=["Standings"])


def _build_pagination_response(response_model, items: list[object], limit: int, offset: int, total: int):
    return response_model(
        items=items,
        pagination=PaginationMetadata(limit=limit, offset=offset, total=total),
    )


def _latest_race(db: Session) -> Race:
    race = db.scalars(
        select(Race)
        .options(joinedload(Race.circuit))
        # Only pick races that have at least one result row — unrun/future races
        # imported from the schedule have 0 results and must be excluded.
        .join(RaceResult, RaceResult.race_id == Race.id)
        .distinct()
        .order_by(Race.race_date.desc(), Race.round_number.desc(), Race.id.desc())
    ).first()
    if race is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No races found")
    return race


def _latest_season(db: Session) -> int:
    season = db.scalar(select(func.max(Race.season)))
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No races found")

    return int(season)


@races_router.get("", response_model=PaginatedResponse[RaceRead])
def list_races(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    season: int | None = Query(default=None, ge=1950),
) -> PaginatedResponse[RaceRead]:
    """Return a paginated list of races, optionally filtered by season."""

    try:
        base = select(Race).options(joinedload(Race.circuit))
        count_base = select(func.count()).select_from(Race)
        if season is not None:
            base = base.where(Race.season == season)
            count_base = count_base.where(Race.season == season)

        total = db.scalar(count_base) or 0
        order = (
            Race.round_number.asc()
            if season is not None
            else Race.race_date.desc()
        )
        statement = (
            base
            .order_by(order, Race.id.asc())
            .offset(offset)
            .limit(limit)
        )
        races = list(db.scalars(statement).all())
    except SQLAlchemyError as exc:  # pragma: no cover - defensive database handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve races",
        ) from exc

    return _build_pagination_response(PaginatedResponse[RaceRead], races, limit, offset, total)


@races_router.get("/upcoming", response_model=UpcomingRaceRead)
def upcoming_race() -> UpcomingRaceRead:
    """Return the next upcoming race from the live FastF1 schedule cache."""

    today = date.today()
    current_year = today.year

    try:
        schedule = fastf1.get_event_schedule(current_year)
        if schedule.empty:
            schedule = fastf1.get_event_schedule(current_year + 1)
        schedule = schedule.copy()
        schedule["EventDate"] = pd.to_datetime(schedule["EventDate"]).dt.date
        future_events = schedule[schedule["EventDate"] >= today].sort_values(["EventDate", "RoundNumber"])
        if future_events.empty:
            raise ValueError("No upcoming race found")

        row = future_events.iloc[0]
        event_date = row["EventDate"]
        circuit_name = str(row.get("CircuitName") or row.get("Location") or row.get("EventName") or "Unknown")
        circuit_country = str(row.get("Country") or "Unknown")
        circuit_location = str(row.get("Location") or circuit_name)
        days_until = (event_date - today).days
    except Exception as exc:  # pragma: no cover - external schedule/network failure
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upcoming race schedule is unavailable",
        ) from exc

    return UpcomingRaceRead(
        season=int(row["Year"] if "Year" in row else current_year),
        round_number=int(row["RoundNumber"]),
        race_name=str(row.get("EventName") or "Upcoming Grand Prix"),
        race_date=event_date,
        circuit={
            "id": 0,
            "name": circuit_name,
            "country": circuit_country,
            "location": circuit_location,
        },
        days_until=days_until,
    )


@races_router.get("/{race_id}", response_model=RaceRead)
def get_race(race_id: int, db: Session = Depends(get_db)) -> RaceRead:
    """Return a single race by identifier."""

    try:
        race = db.scalars(
            select(Race)
            .options(joinedload(Race.circuit))
            .where(Race.id == race_id)
        ).first()
    except SQLAlchemyError as exc:  # pragma: no cover - defensive database handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve race",
        ) from exc

    if race is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Race not found")

    return race


@races_router.get("/{race_id}/results", response_model=LatestRaceResultsResponse)
def get_race_results(race_id: int, db: Session = Depends(get_db)) -> LatestRaceResultsResponse:
    """Return race results for a specific race by id."""

    try:
        race = db.scalars(
            select(Race).options(joinedload(Race.circuit)).where(Race.id == race_id)
        ).first()
        if race is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Race not found")

        results = list(
            db.scalars(
                select(RaceResult)
                .options(joinedload(RaceResult.driver), joinedload(RaceResult.constructor))
                .where(RaceResult.race_id == race_id)
                .order_by(RaceResult.finish_position.asc().nulls_last(), RaceResult.id.asc())
            ).all()
        )
    except HTTPException:
        raise
    except SQLAlchemyError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve race results",
        ) from exc

    return LatestRaceResultsResponse(race=race, results=results)


@races_router.get("/{race_id}/qualifying", response_model=LatestQualifyingResultsResponse)
def get_race_qualifying(race_id: int, db: Session = Depends(get_db)) -> LatestQualifyingResultsResponse:
    """Return qualifying results for a specific race by id."""

    try:
        race = db.scalars(
            select(Race).options(joinedload(Race.circuit)).where(Race.id == race_id)
        ).first()
        if race is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Race not found")

        results = list(
            db.scalars(
                select(QualifyingResult)
                .options(joinedload(QualifyingResult.driver), joinedload(QualifyingResult.constructor))
                .where(QualifyingResult.race_id == race_id)
                .order_by(QualifyingResult.qualifying_position.asc().nulls_last(), QualifyingResult.id.asc())
            ).all()
        )
    except HTTPException:
        raise
    except SQLAlchemyError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve qualifying results",
        ) from exc

    return LatestQualifyingResultsResponse(race=race, results=results)


@drivers_router.get("", response_model=PaginatedResponse[DriverRead])
def list_drivers(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[DriverRead]:
    """Return a paginated list of drivers."""

    try:
        total = db.scalar(select(func.count()).select_from(Driver)) or 0
        statement = (
            select(Driver)
            .order_by(Driver.driver_code.asc(), Driver.id.asc())
            .offset(offset)
            .limit(limit)
        )
        drivers = list(db.scalars(statement).all())
    except SQLAlchemyError as exc:  # pragma: no cover - defensive database handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve drivers",
        ) from exc

    return _build_pagination_response(PaginatedResponse[DriverRead], drivers, limit, offset, total)


@drivers_router.get("/{driver_id}", response_model=DriverDetailRead)
def get_driver(driver_id: int, db: Session = Depends(get_db)) -> DriverDetailRead:
    """Return a driver's full detail: bio, career stats, and recent race results."""

    try:
        driver = db.scalar(select(Driver).where(Driver.id == driver_id))
    except SQLAlchemyError as exc:  # pragma: no cover - defensive database handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve driver",
        ) from exc

    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")

    try:
        # ── Career-wide aggregate stats ─────────────────────────────────────
        agg = db.execute(
            select(
                func.count(RaceResult.id).label("total_races"),
                func.coalesce(func.sum(RaceResult.points), 0).label("total_points"),
                func.coalesce(
                    func.sum(case((RaceResult.finish_position == 1, 1), else_=0)), 0
                ).label("total_wins"),
                func.coalesce(
                    func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)), 0
                ).label("total_podiums"),
                func.avg(
                    case(
                        (RaceResult.finish_position.is_not(None), RaceResult.finish_position),
                        else_=None,
                    )
                ).label("avg_finish"),
            ).where(RaceResult.driver_id == driver_id)
        ).one()

        # ── Last 10 race results (most-recent first) ────────────────────────
        recent_rows = db.execute(
            select(
                Race.id.label("race_id"),
                Race.season,
                Race.round_number,
                Race.race_name,
                Race.race_date,
                Circuit.name.label("circuit_name"),
                Circuit.country.label("circuit_country"),
                Constructor.name.label("constructor_name"),
                RaceResult.grid_position,
                RaceResult.finish_position,
                RaceResult.points,
                RaceResult.status,
            )
            .join(Race, RaceResult.race_id == Race.id)
            .join(Circuit, Race.circuit_id == Circuit.id)
            .join(Constructor, RaceResult.constructor_id == Constructor.id)
            .where(RaceResult.driver_id == driver_id)
            .order_by(Race.race_date.desc(), Race.round_number.desc())
            .limit(10)
        ).all()

    except SQLAlchemyError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve driver detail",
        ) from exc

    avg_finish = float(agg.avg_finish) if agg.avg_finish is not None else None

    recent_results = [
        DriverRecentResultRead(
            race_id=row.race_id,
            season=row.season,
            round_number=row.round_number,
            race_name=row.race_name,
            race_date=row.race_date,
            circuit_name=row.circuit_name,
            circuit_country=row.circuit_country,
            constructor_name=row.constructor_name,
            grid_position=row.grid_position,
            finish_position=row.finish_position,
            points=row.points,
            status=row.status,
        )
        for row in recent_rows
    ]

    return DriverDetailRead(
        driver=DriverRead.model_validate(driver),
        total_races=int(agg.total_races),
        total_wins=int(agg.total_wins),
        total_podiums=int(agg.total_podiums),
        total_points=float(agg.total_points),
        avg_finish_position=avg_finish,
        recent_results=recent_results,
    )


@constructors_router.get("", response_model=PaginatedResponse[ConstructorRead])
def list_constructors(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[ConstructorRead]:
    """Return a paginated list of constructors."""

    try:
        total = db.scalar(select(func.count()).select_from(Constructor)) or 0
        statement = (
            select(Constructor)
            .order_by(Constructor.name.asc(), Constructor.id.asc())
            .offset(offset)
            .limit(limit)
        )
        constructors = list(db.scalars(statement).all())
    except SQLAlchemyError as exc:  # pragma: no cover - defensive database handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve constructors",
        ) from exc

    return _build_pagination_response(PaginatedResponse[ConstructorRead], constructors, limit, offset, total)


@constructors_router.get("/{constructor_id}", response_model=ConstructorRead)
def get_constructor(constructor_id: int, db: Session = Depends(get_db)) -> ConstructorRead:
    """Return a single constructor by identifier."""

    try:
        constructor = db.scalar(select(Constructor).where(Constructor.id == constructor_id))
    except SQLAlchemyError as exc:  # pragma: no cover - defensive database handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve constructor",
        ) from exc

    if constructor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Constructor not found")

    return constructor


@standings_router.get("/drivers", response_model=PaginatedResponse[DriverStandingRead])
def list_driver_standings(
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    season: int | None = Query(default=None, ge=1950),
) -> PaginatedResponse[DriverStandingRead]:
    """Return aggregated driver standings for a season."""

    try:
        resolved_season = season or _latest_season(db)
        standings_query = (
            select(
                Driver.id.label("driver_id"),
                Driver.driver_code,
                Driver.first_name,
                Driver.last_name,
                Driver.nationality,
                func.coalesce(func.sum(RaceResult.points), 0).label("points"),
                func.count(RaceResult.id).label("races"),
                func.coalesce(func.sum(case((RaceResult.finish_position == 1, 1), else_=0)), 0).label("wins"),
                func.coalesce(func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)), 0).label("podiums"),
            )
            .join(RaceResult, RaceResult.driver_id == Driver.id)
            .join(Race, RaceResult.race_id == Race.id)
            .where(Race.season == resolved_season)
            .group_by(Driver.id)
            .order_by(
                desc("points"),
                desc("wins"),
                desc("podiums"),
                Driver.driver_code.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        count_query = (
            select(func.count(func.distinct(Driver.id)))
            .join(RaceResult, RaceResult.driver_id == Driver.id)
            .join(Race, RaceResult.race_id == Race.id)
            .where(Race.season == resolved_season)
        )

        total = db.scalar(count_query) or 0
        rows = db.execute(standings_query).all()
    except SQLAlchemyError as exc:  # pragma: no cover - defensive database handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve driver standings",
        ) from exc

    items = [
        DriverStandingRead(
            position=offset + index + 1,
            points=float(row.points or 0),
            wins=int(row.wins or 0),
            podiums=int(row.podiums or 0),
            races=int(row.races or 0),
            driver=DriverRead(
                id=int(row.driver_id),
                driver_code=row.driver_code,
                first_name=row.first_name,
                last_name=row.last_name,
                nationality=row.nationality,
            ),
        )
        for index, row in enumerate(rows)
    ]

    return _build_pagination_response(PaginatedResponse[DriverStandingRead], items, limit, offset, total)


@standings_router.get("/constructors", response_model=PaginatedResponse[ConstructorStandingRead])
def list_constructor_standings(
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    season: int | None = Query(default=None, ge=1950),
) -> PaginatedResponse[ConstructorStandingRead]:
    """Return aggregated constructor standings for a season."""

    try:
        resolved_season = season or _latest_season(db)
        standings_query = (
            select(
                Constructor.id.label("constructor_id"),
                Constructor.name,
                Constructor.nationality,
                func.coalesce(func.sum(RaceResult.points), 0).label("points"),
                func.count(RaceResult.id).label("races"),
                func.coalesce(func.sum(case((RaceResult.finish_position == 1, 1), else_=0)), 0).label("wins"),
                func.coalesce(func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)), 0).label("podiums"),
            )
            .join(RaceResult, RaceResult.constructor_id == Constructor.id)
            .join(Race, RaceResult.race_id == Race.id)
            .where(Race.season == resolved_season)
            .group_by(Constructor.id)
            .order_by(
                desc("points"),
                desc("wins"),
                desc("podiums"),
                Constructor.name.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        count_query = (
            select(func.count(func.distinct(Constructor.id)))
            .join(RaceResult, RaceResult.constructor_id == Constructor.id)
            .join(Race, RaceResult.race_id == Race.id)
            .where(Race.season == resolved_season)
        )

        total = db.scalar(count_query) or 0
        rows = db.execute(standings_query).all()
    except SQLAlchemyError as exc:  # pragma: no cover - defensive database handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve constructor standings",
        ) from exc

    items = [
        ConstructorStandingRead(
            position=offset + index + 1,
            points=float(row.points or 0),
            wins=int(row.wins or 0),
            podiums=int(row.podiums or 0),
            races=int(row.races or 0),
            constructor=ConstructorRead(
                id=int(row.constructor_id),
                name=row.name,
                nationality=row.nationality,
            ),
        )
        for index, row in enumerate(rows)
    ]

    return _build_pagination_response(PaginatedResponse[ConstructorStandingRead], items, limit, offset, total)


@results_router.get("/latest", response_model=LatestRaceResultsResponse)
def latest_results(db: Session = Depends(get_db)) -> LatestRaceResultsResponse:
    """Return the latest race and its race results."""

    try:
        race = _latest_race(db)
        results = list(
            db.scalars(
                select(RaceResult)
                .options(joinedload(RaceResult.driver), joinedload(RaceResult.constructor))
                .where(RaceResult.race_id == race.id)
                .order_by(RaceResult.finish_position.asc().nulls_last(), RaceResult.id.asc())
            ).all()
        )
    except SQLAlchemyError as exc:  # pragma: no cover - defensive database handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve latest results",
        ) from exc

    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No race results found")

    return LatestRaceResultsResponse(race=race, results=results)


@qualifying_router.get("/latest", response_model=LatestQualifyingResultsResponse)
def latest_qualifying(db: Session = Depends(get_db)) -> LatestQualifyingResultsResponse:
    """Return the latest race and its qualifying results."""

    try:
        race = _latest_race(db)
        results = list(
            db.scalars(
                select(QualifyingResult)
                .options(joinedload(QualifyingResult.driver), joinedload(QualifyingResult.constructor))
                .where(QualifyingResult.race_id == race.id)
                .order_by(QualifyingResult.qualifying_position.asc().nulls_last(), QualifyingResult.id.asc())
            ).all()
        )
    except SQLAlchemyError as exc:  # pragma: no cover - defensive database handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve latest qualifying results",
        ) from exc

    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No qualifying results found")

    return LatestQualifyingResultsResponse(race=race, results=results)



