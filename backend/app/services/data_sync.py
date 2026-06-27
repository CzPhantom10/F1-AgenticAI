"""Automatic database synchronisation service for Racecraft AI.

On every backend startup this service:
1. Determines the latest *completed* race stored in the database.
2. Queries FastF1 for the latest *completed* race available.
3. Imports only the rounds that are missing — never the entire season.

A manual trigger is also exposed via ``POST /admin/sync``.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import fastf1
import pandas as pd
from sqlalchemy import func, select

from app.agents.data_agent import DataAgent
from app.database.db import SessionLocal
from app.models.driver import Driver
from app.models.constructor import Constructor
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.qualifying_result import QualifyingResult

if TYPE_CHECKING:
    pass


LOGGER = logging.getLogger(__name__)

# Module-level flag — prevents a second sync if create_app() is called twice
# (e.g. during pytest collection with --import-mode=importlib).
_startup_sync_done: bool = False


# ── Internal result dataclasses ───────────────────────────────────────────────

@dataclass
class RaceImportDetail:
    """Per-round import outcome."""

    season: int
    round_number: int
    race_name: str
    race_results_imported: int
    qualifying_results_imported: int
    success: bool
    error: str | None = None


@dataclass
class SyncResult:
    """Aggregate outcome of a single sync run."""

    updated: bool = False
    new_races: int = 0
    drivers_updated: bool = False
    constructors_updated: bool = False
    seasons_touched: list[int] = field(default_factory=list)
    races: list[RaceImportDetail] = field(default_factory=list)
    message: str = "No new races found — database is already up to date."


# ── DataSyncService ───────────────────────────────────────────────────────────

class DataSyncService:
    """Detects and imports missing F1 race data incrementally.

    All heavy lifting (fetching from FastF1, building ORM rows, upserting) is
    delegated to the existing ``DataAgent`` — this service only handles the
    *orchestration*: what is missing and what to import.
    """

    def __init__(self) -> None:
        self._agent = DataAgent()

    # ── Public API ────────────────────────────────────────────────────────────

    def sync_missing_races(self) -> SyncResult:
        """Compare the database with FastF1 and import any missing rounds.

        Returns a ``SyncResult`` describing everything that happened.
        Never raises — all exceptions are caught and surfaced inside the result
        so callers (startup hook, HTTP endpoint) can decide what to do.
        """
        LOGGER.info("[DataSync] Checking for new F1 race data...")

        result = SyncResult()

        # ── 1. Latest completed race in DB ────────────────────────────────────
        try:
            db_latest = self._get_latest_db_race()
        except Exception as exc:
            msg = f"[DataSync] Failed to query database for latest race: {exc}"
            LOGGER.error(msg)
            result.message = msg
            return result

        if db_latest is None:
            LOGGER.info("[DataSync] Database is empty — nothing to diff against.")
            result.message = "Database is empty. Run the historical import script first."
            return result

        db_season, db_round, db_race_name = db_latest
        LOGGER.info(
            "[DataSync] Latest race in database: %s — Round %s (%s)",
            db_season,
            db_round,
            db_race_name,
        )

        # ── 2. Latest completed race from FastF1 ──────────────────────────────
        current_year = datetime.date.today().year
        try:
            fastf1_rounds = self._get_completed_rounds(current_year)
        except Exception as exc:
            msg = f"[DataSync] FastF1 unavailable — serving existing data. Error: {exc}"
            LOGGER.warning(msg)
            result.message = msg
            return result

        # Also check previous year in January (new season not yet released)
        if not fastf1_rounds:
            LOGGER.info(
                "[DataSync] No completed rounds found for %s yet.", current_year
            )
            result.message = f"No completed rounds found for {current_year} yet."
            return result

        latest_ff1 = fastf1_rounds[-1]
        ff1_season = latest_ff1["season"]
        ff1_round = latest_ff1["round"]
        ff1_name = latest_ff1["name"]
        LOGGER.info(
            "[DataSync] Latest race from FastF1: %s — Round %s (%s)",
            ff1_season,
            ff1_round,
            ff1_name,
        )

        # ── 3. Identify missing rounds ────────────────────────────────────────
        missing = self._find_missing_rounds(
            db_season, db_round, fastf1_rounds
        )

        if not missing:
            LOGGER.info("[DataSync] Database is already up to date.")
            result.message = "Database is already up to date."
            return result

        LOGGER.info(
            "[DataSync] Importing %s missing race(s)...", len(missing)
        )

        # ── 4. Import each missing round ──────────────────────────────────────
        drivers_before = self._count_rows(Driver)
        constructors_before = self._count_rows(Constructor)

        for entry in missing:
            detail = self._import_single_round(entry["season"], entry["round"], entry["name"])
            result.races.append(detail)
            if detail.success:
                result.new_races += 1
                if entry["season"] not in result.seasons_touched:
                    result.seasons_touched.append(entry["season"])

        drivers_after = self._count_rows(Driver)
        constructors_after = self._count_rows(Constructor)

        result.updated = result.new_races > 0
        result.drivers_updated = drivers_after > drivers_before
        result.constructors_updated = constructors_after > constructors_before

        if result.new_races > 0:
            result.message = (
                f"Imported {result.new_races} new race(s) successfully."
            )
            LOGGER.info("[DataSync] %s", result.message)
        else:
            result.message = "Sync completed but no races could be imported (check logs)."
            LOGGER.warning("[DataSync] %s", result.message)

        return result

    def run_startup_sync(self) -> None:
        """Run ``sync_missing_races()`` once at application startup.

        Catches all exceptions so a FastF1 outage or database issue during
        startup never prevents the backend from starting up.  Uses a
        module-level flag to ensure this runs exactly once per process even if
        ``create_app()`` is somehow called multiple times.
        """
        global _startup_sync_done  # noqa: PLW0603
        if _startup_sync_done:
            LOGGER.debug("[DataSync] Startup sync already ran — skipping.")
            return

        _startup_sync_done = True

        try:
            result = self.sync_missing_races()
            LOGGER.info("[DataSync] Startup sync complete: %s", result.message)
        except Exception as exc:
            LOGGER.error(
                "[DataSync] Startup sync failed unexpectedly: %s", exc,
                exc_info=True,
            )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_latest_db_race(self) -> tuple[int, int, str] | None:
        """Return ``(season, round_number, race_name)`` of the most recent
        race in the DB that has at least one RaceResult row."""
        with SessionLocal() as session:
            row = session.execute(
                select(Race.season, Race.round_number, Race.race_name)
                .join(RaceResult, RaceResult.race_id == Race.id)
                .group_by(Race.id)
                .having(func.count(RaceResult.id) > 0)
                .order_by(Race.race_date.desc(), Race.round_number.desc())
                .limit(1)
            ).first()

        if row is None:
            return None
        return int(row.season), int(row.round_number), str(row.race_name)

    def _get_completed_rounds(self, year: int) -> list[dict]:
        """Return all completed race rounds for *year* from FastF1.

        A round is considered 'completed' when its ``EventDate`` is in the past
        and it is a conventional race (not a pre-season test, i.e. RoundNumber > 0).
        """
        today = datetime.date.today()
        try:
            schedule = fastf1.get_event_schedule(year, include_testing=False)
        except Exception as exc:
            LOGGER.warning("[DataSync] FastF1 schedule fetch failed for %s: %s", year, exc)
            raise

        if schedule is None or schedule.empty:
            return []

        completed: list[dict] = []
        for row in schedule.to_dict(orient="records"):
            round_num = row.get("RoundNumber")
            event_date = row.get("EventDate")
            event_name = row.get("EventName", f"Round {round_num}")

            if not round_num or int(round_num) <= 0:
                continue

            if event_date is None or pd.isna(event_date):
                continue

            race_date = pd.to_datetime(event_date).date()
            if race_date > today:
                continue  # future race — skip

            completed.append(
                {"season": year, "round": int(round_num), "name": str(event_name), "date": race_date}
            )

        # Sort by date ascending so we import chronologically
        completed.sort(key=lambda r: (r["season"], r["round"]))
        return completed

    def _find_missing_rounds(
        self,
        db_season: int,
        db_round: int,
        fastf1_rounds: list[dict],
    ) -> list[dict]:
        """Return entries from *fastf1_rounds* that come after the latest DB race.

        Additionally fetch the DB for any rounds within the current season that
        exist in FastF1 but are not yet in the database (handles gaps).
        """
        # Rounds strictly after the latest DB entry
        missing = [
            r for r in fastf1_rounds
            if (r["season"], r["round"]) > (db_season, db_round)
        ]

        # Also catch any rounds in the same season that may have been skipped
        same_season_ff1 = {
            r["round"] for r in fastf1_rounds if r["season"] == db_season
        }
        with SessionLocal() as session:
            db_rounds_in_season = set(
                session.execute(
                    select(Race.round_number)
                    .join(RaceResult, RaceResult.race_id == Race.id)
                    .where(Race.season == db_season)
                    .group_by(Race.round_number)
                    .having(func.count(RaceResult.id) > 0)
                ).scalars().all()
            )

        gap_rounds = same_season_ff1 - db_rounds_in_season
        for r in fastf1_rounds:
            if r["season"] == db_season and r["round"] in gap_rounds:
                # Avoid duplicating entries already in `missing`
                if r not in missing:
                    missing.insert(0, r)

        # Re-sort to keep chronological order
        missing.sort(key=lambda r: (r["season"], r["round"]))
        return missing

    def _import_single_round(
        self, season: int, round_number: int, race_name: str
    ) -> RaceImportDetail:
        """Delegate the actual import of one round to DataAgent.

        Wraps the call in a try/except so a failure for one round does not
        prevent subsequent rounds from being imported.
        """
        LOGGER.info(
            "[DataSync] Importing %s Round %s — %s...",
            season, round_number, race_name,
        )
        try:
            race_results, qualifying_results = self._agent.fetch_race_by_round(
                season, round_number
            )
            return RaceImportDetail(
                season=season,
                round_number=round_number,
                race_name=race_name,
                race_results_imported=len(race_results),
                qualifying_results_imported=len(qualifying_results),
                success=True,
            )
        except Exception as exc:
            msg = str(exc)
            LOGGER.error(
                "[DataSync] Failed to import %s Round %s: %s",
                season, round_number, msg,
                exc_info=True,
            )
            return RaceImportDetail(
                season=season,
                round_number=round_number,
                race_name=race_name,
                race_results_imported=0,
                qualifying_results_imported=0,
                success=False,
                error=msg,
            )

    @staticmethod
    def _count_rows(model) -> int:  # type: ignore[type-arg]
        """Return the total row count for *model*."""
        with SessionLocal() as session:
            return session.scalar(select(func.count()).select_from(model)) or 0


__all__ = ["DataSyncService", "SyncResult", "RaceImportDetail"]
