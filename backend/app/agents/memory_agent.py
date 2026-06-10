"""Memory Agent — build and persist pre-computed F1 driver/constructor insights.

This agent reads existing race and qualifying data from the database,
computes statistical summaries per driver and per constructor, and writes
them into the driver_insights / constructor_insights tables.

No external APIs are called — it is entirely self-contained on SQLite.
"""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass, field

from sqlalchemy import case, desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.circuit import Circuit
from app.models.constructor import Constructor
from app.models.driver import Driver
from app.models.memory import ConstructorInsight, DriverInsight, CircuitInsight
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.race_result import RaceResult

LOGGER = logging.getLogger(__name__)

# How many recent races to include in the "form" snapshot
RECENT_RACES_WINDOW = 5


# ── Result containers ────────────────────────────────────────────────────────


@dataclass
class RebuildStats:
    """Summary returned after a full memory rebuild."""

    drivers_processed: int = 0
    constructors_processed: int = 0
    circuits_processed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


# ── Memory Agent ─────────────────────────────────────────────────────────────


class MemoryAgent:
    """Compute and persist performance insights for all drivers, constructors, and circuits."""

    # ── Public entry points ──────────────────────────────────────────────────

    def rebuild_all(self, session: Session) -> RebuildStats:
        """Rebuild every driver, constructor, and circuit insight."""
        stats = RebuildStats()

        drivers = list(session.scalars(select(Driver)).all())
        for driver in drivers:
            try:
                self._rebuild_driver(session, driver)
                stats.drivers_processed += 1
            except SQLAlchemyError as exc:
                msg = f"Driver {driver.id} ({driver.driver_code}): {exc}"
                LOGGER.error(msg)
                stats.errors.append(msg)

        constructors = list(session.scalars(select(Constructor)).all())
        for constructor in constructors:
            try:
                self._rebuild_constructor(session, constructor)
                stats.constructors_processed += 1
            except SQLAlchemyError as exc:
                msg = f"Constructor {constructor.id} ({constructor.name}): {exc}"
                LOGGER.error(msg)
                stats.errors.append(msg)

        circuits = list(session.scalars(select(Circuit)).all())
        for circuit in circuits:
            try:
                self._rebuild_circuit(session, circuit)
                stats.circuits_processed += 1
            except SQLAlchemyError as exc:
                msg = f"Circuit {circuit.id} ({circuit.name}): {exc}"
                LOGGER.error(msg)
                stats.errors.append(msg)

        try:
            session.commit()
        except SQLAlchemyError as exc:
            session.rollback()
            raise

        LOGGER.info(
            "Memory rebuild complete: %d drivers, %d constructors, %d circuits, %d errors",
            stats.drivers_processed,
            stats.constructors_processed,
            stats.circuits_processed,
            len(stats.errors),
        )
        return stats

    def get_driver_insight(self, session: Session, driver_id: int) -> DriverInsight | None:
        """Return the stored insight for a driver, or None if not built yet."""
        return session.scalar(
            select(DriverInsight).where(DriverInsight.driver_id == driver_id)
        )

    def get_constructor_insight(self, session: Session, constructor_id: int) -> ConstructorInsight | None:
        """Return the stored insight for a constructor, or None if not built yet."""
        return session.scalar(
            select(ConstructorInsight).where(ConstructorInsight.constructor_id == constructor_id)
        )

    def get_circuit_insight(self, session: Session, circuit_id: int) -> CircuitInsight | None:
        """Return the stored insight for a circuit, or None if not built yet."""
        return session.scalar(
            select(CircuitInsight).where(CircuitInsight.circuit_id == circuit_id)
        )

    # ── Driver rebuild ───────────────────────────────────────────────────────

    def _rebuild_driver(self, session: Session, driver: Driver) -> None:
        """Compute all stats for one driver and upsert the DriverInsight row."""

        # ── Career-wide aggregates ───────────────────────────────────────────
        agg = session.execute(
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
            ).where(RaceResult.driver_id == driver.id)
        ).one()

        avg_qual_row = session.execute(
            select(
                func.avg(
                    case(
                        (QualifyingResult.qualifying_position.is_not(None), QualifyingResult.qualifying_position),
                        else_=None,
                    )
                ).label("avg_qual")
            ).where(QualifyingResult.driver_id == driver.id)
        ).one()

        # ── Per-season breakdown ─────────────────────────────────────────────
        season_rows = session.execute(
            select(
                Race.season,
                func.count(RaceResult.id).label("races"),
                func.coalesce(func.sum(RaceResult.points), 0).label("points"),
                func.coalesce(
                    func.sum(case((RaceResult.finish_position == 1, 1), else_=0)), 0
                ).label("wins"),
                func.coalesce(
                    func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)), 0
                ).label("podiums"),
            )
            .join(Race, RaceResult.race_id == Race.id)
            .where(RaceResult.driver_id == driver.id)
            .group_by(Race.season)
            .order_by(Race.season.asc())
        ).all()

        season_breakdown = [
            {
                "season": row.season,
                "races": int(row.races),
                "wins": int(row.wins),
                "podiums": int(row.podiums),
                "points": float(row.points or 0),
            }
            for row in season_rows
        ]

        # ── Recent form (last N races, most recent first) ────────────────────
        recent_rows = session.execute(
            select(
                Race.race_name,
                Race.season,
                Race.round_number,
                Race.race_date,
                RaceResult.finish_position,
                RaceResult.grid_position,
                RaceResult.points,
                RaceResult.status,
            )
            .join(Race, RaceResult.race_id == Race.id)
            .where(RaceResult.driver_id == driver.id)
            .order_by(Race.race_date.desc(), Race.round_number.desc())
            .limit(RECENT_RACES_WINDOW)
        ).all()

        recent_form = [
            {
                "race": row.race_name,
                "season": row.season,
                "round": row.round_number,
                "date": row.race_date.isoformat() if row.race_date else None,
                "finish": row.finish_position,
                "grid": row.grid_position,
                "points": float(row.points or 0),
                "status": row.status,
            }
            for row in recent_rows
        ]

        # ── Upsert ───────────────────────────────────────────────────────────
        insight = session.scalar(
            select(DriverInsight).where(DriverInsight.driver_id == driver.id)
        )
        if insight is None:
            insight = DriverInsight(driver_id=driver.id)
            session.add(insight)

        insight.total_races = int(agg.total_races or 0)
        insight.total_wins = int(agg.total_wins or 0)
        insight.total_podiums = int(agg.total_podiums or 0)
        insight.total_points = float(agg.total_points or 0)
        insight.avg_finish_position = float(agg.avg_finish) if agg.avg_finish is not None else None
        insight.avg_qualifying_position = (
            float(avg_qual_row.avg_qual) if avg_qual_row.avg_qual is not None else None
        )
        insight.recent_form_json = json.dumps(recent_form)
        insight.season_breakdown_json = json.dumps(season_breakdown)
        insight.rebuilt_at = datetime.datetime.utcnow()

    # ── Constructor rebuild ──────────────────────────────────────────────────

    def _rebuild_constructor(self, session: Session, constructor: Constructor) -> None:
        """Compute all stats for one constructor and upsert the ConstructorInsight row."""

        # ── Career-wide aggregates ───────────────────────────────────────────
        agg = session.execute(
            select(
                func.count(RaceResult.id).label("total_races"),
                func.coalesce(func.sum(RaceResult.points), 0).label("total_points"),
                func.coalesce(
                    func.sum(case((RaceResult.finish_position == 1, 1), else_=0)), 0
                ).label("total_wins"),
                func.coalesce(
                    func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)), 0
                ).label("total_podiums"),
            ).where(RaceResult.constructor_id == constructor.id)
        ).one()

        avg_pts = (
            float(agg.total_points) / int(agg.total_races)
            if agg.total_races and int(agg.total_races) > 0
            else None
        )

        # ── Per-season breakdown ─────────────────────────────────────────────
        season_rows = session.execute(
            select(
                Race.season,
                func.count(RaceResult.id).label("races"),
                func.coalesce(func.sum(RaceResult.points), 0).label("points"),
                func.coalesce(
                    func.sum(case((RaceResult.finish_position == 1, 1), else_=0)), 0
                ).label("wins"),
                func.coalesce(
                    func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)), 0
                ).label("podiums"),
            )
            .join(Race, RaceResult.race_id == Race.id)
            .where(RaceResult.constructor_id == constructor.id)
            .group_by(Race.season)
            .order_by(Race.season.asc())
        ).all()

        season_breakdown = [
            {
                "season": row.season,
                "races": int(row.races),
                "wins": int(row.wins),
                "podiums": int(row.podiums),
                "points": float(row.points or 0),
                "avg_points_per_race": (
                    float(row.points or 0) / int(row.races)
                    if row.races and int(row.races) > 0
                    else None
                ),
            }
            for row in season_rows
        ]

        # ── Recent form: last N race-events the constructor participated in ──
        # A constructor may have 2 drivers per race, so we aggregate per race.
        recent_race_ids_rows = session.execute(
            select(RaceResult.race_id)
            .where(RaceResult.constructor_id == constructor.id)
            .distinct()
            .join(Race, RaceResult.race_id == Race.id)
            .order_by(Race.race_date.desc(), Race.round_number.desc())
            .limit(RECENT_RACES_WINDOW)
        ).all()
        recent_race_ids = [row.race_id for row in recent_race_ids_rows]

        if recent_race_ids:
            recent_rows = session.execute(
                select(
                    Race.race_name,
                    Race.season,
                    Race.round_number,
                    Race.race_date,
                    func.coalesce(func.sum(RaceResult.points), 0).label("points"),
                    func.coalesce(
                        func.sum(case((RaceResult.finish_position == 1, 1), else_=0)), 0
                    ).label("wins"),
                    func.coalesce(
                        func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)), 0
                    ).label("podiums"),
                )
                .join(Race, RaceResult.race_id == Race.id)
                .where(
                    RaceResult.constructor_id == constructor.id,
                    RaceResult.race_id.in_(recent_race_ids),
                )
                .group_by(Race.id)
                .order_by(Race.race_date.desc(), Race.round_number.desc())
            ).all()

            recent_form = [
                {
                    "race": row.race_name,
                    "season": row.season,
                    "round": row.round_number,
                    "date": row.race_date.isoformat() if row.race_date else None,
                    "points": float(row.points or 0),
                    "wins": int(row.wins or 0),
                    "podiums": int(row.podiums or 0),
                }
                for row in recent_rows
            ]
        else:
            recent_form = []

        # ── Upsert ───────────────────────────────────────────────────────────
        insight = session.scalar(
            select(ConstructorInsight).where(ConstructorInsight.constructor_id == constructor.id)
        )
        if insight is None:
            insight = ConstructorInsight(constructor_id=constructor.id)
            session.add(insight)

        insight.total_races = int(agg.total_races or 0)
        insight.total_wins = int(agg.total_wins or 0)
        insight.total_podiums = int(agg.total_podiums or 0)
        insight.total_points = float(agg.total_points or 0)
        insight.avg_points_per_race = avg_pts
        insight.recent_form_json = json.dumps(recent_form)
        insight.season_breakdown_json = json.dumps(season_breakdown)
        insight.rebuilt_at = datetime.datetime.utcnow()

    # ── Circuit rebuild ───────────────────────────────────────────────────────

    def _rebuild_circuit(self, session: Session, circuit: Circuit) -> None:
        """Compute all stats for one circuit and upsert the CircuitInsight row."""

        # 1. Historical winners
        winners_rows = session.execute(
            select(
                Race.season,
                Race.round_number,
                Driver.id.label("driver_id"),
                Driver.first_name,
                Driver.last_name,
                Constructor.name.label("constructor_name")
            )
            .join(RaceResult, RaceResult.race_id == Race.id)
            .join(Driver, RaceResult.driver_id == Driver.id)
            .join(Constructor, RaceResult.constructor_id == Constructor.id)
            .where(Race.circuit_id == circuit.id, RaceResult.finish_position == 1)
            .order_by(Race.season.desc(), Race.round_number.desc())
        ).all()

        historical_winners = [
            {
                "season": row.season,
                "round": row.round_number,
                "driver_id": row.driver_id,
                "driver_name": f"{row.first_name} {row.last_name}",
                "constructor_name": row.constructor_name,
            }
            for row in winners_rows
        ]

        # 2. Best drivers
        drivers_rows = session.execute(
            select(
                Driver.id.label("driver_id"),
                Driver.first_name,
                Driver.last_name,
                func.count(RaceResult.id).label("races"),
                func.sum(case((RaceResult.finish_position == 1, 1), else_=0)).label("wins"),
                func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)).label("podiums"),
                func.avg(case((RaceResult.finish_position.is_not(None), RaceResult.finish_position), else_=None)).label("avg_finish"),
                func.coalesce(func.sum(RaceResult.points), 0).label("points")
            )
            .join(Race, RaceResult.race_id == Race.id)
            .join(Driver, RaceResult.driver_id == Driver.id)
            .where(Race.circuit_id == circuit.id)
            .group_by(Driver.id)
        ).all()

        best_drivers = [
            {
                "driver_id": row.driver_id,
                "driver_name": f"{row.first_name} {row.last_name}",
                "races": int(row.races),
                "wins": int(row.wins or 0),
                "podiums": int(row.podiums or 0),
                "avg_finish": float(row.avg_finish) if row.avg_finish is not None else None,
                "points": float(row.points)
            }
            for row in drivers_rows
        ]
        # Sort by: wins (desc), podiums (desc), avg_finish (asc)
        best_drivers.sort(
            key=lambda x: (
                -x["wins"],
                -x["podiums"],
                x["avg_finish"] if x["avg_finish"] is not None else 999.0
            )
        )

        # 3. Best constructors
        constructors_rows = session.execute(
            select(
                Constructor.id.label("constructor_id"),
                Constructor.name.label("constructor_name"),
                func.count(RaceResult.id).label("entries"),
                func.sum(case((RaceResult.finish_position == 1, 1), else_=0)).label("wins"),
                func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)).label("podiums"),
                func.coalesce(func.sum(RaceResult.points), 0).label("points"),
                func.avg(case((RaceResult.finish_position.is_not(None), RaceResult.finish_position), else_=None)).label("avg_finish"),
            )
            .join(Race, RaceResult.race_id == Race.id)
            .join(Constructor, RaceResult.constructor_id == Constructor.id)
            .where(Race.circuit_id == circuit.id)
            .group_by(Constructor.id)
        ).all()

        best_constructors = [
            {
                "constructor_id": row.constructor_id,
                "constructor_name": row.constructor_name,
                "entries": int(row.entries),
                "wins": int(row.wins or 0),
                "podiums": int(row.podiums or 0),
                "points": float(row.points),
                "avg_finish": float(row.avg_finish) if row.avg_finish is not None else None,
            }
            for row in constructors_rows
        ]
        # Sort by: wins * 100 + podiums * 20 + points - avg_finish * 10
        def get_constructor_score(c):
            w = c["wins"]
            p = c["podiums"]
            pts = c["points"]
            af = c["avg_finish"] if c["avg_finish"] is not None else 20.0
            return w * 100 + p * 20 + pts - af * 10
        best_constructors.sort(key=lambda x: -get_constructor_score(x))

        # Upsert
        insight = session.scalar(
            select(CircuitInsight).where(CircuitInsight.circuit_id == circuit.id)
        )
        if insight is None:
            insight = CircuitInsight(circuit_id=circuit.id)
            session.add(insight)

        insight.historical_winners_json = json.dumps(historical_winners)
        insight.best_drivers_json = json.dumps(best_drivers)
        insight.best_constructors_json = json.dumps(best_constructors)
        insight.rebuilt_at = datetime.datetime.utcnow()


__all__ = ["MemoryAgent", "RebuildStats"]
