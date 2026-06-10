"""FastF1-backed data agent for PitWall AI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

import fastf1
import pandas as pd
from pandas import DataFrame
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.circuit import Circuit
from app.models.constructor import Constructor
from app.models.driver import Driver
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.race_result import RaceResult


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RaceRecord:
    """Normalized race metadata ready for persistence."""

    season: int
    round_number: int
    race_name: str
    race_date: date
    circuit_name: str
    circuit_country: str
    circuit_location: str


@dataclass(slots=True)
class RaceResultRecord:
    """Normalized race result metadata ready for persistence."""

    race_id: int
    driver_id: int
    constructor_id: int
    grid_position: int | None
    finish_position: int | None
    points: float | None
    status: str


@dataclass(slots=True)
class QualifyingResultRecord:
    """Normalized qualifying result metadata ready for persistence."""

    race_id: int
    driver_id: int
    constructor_id: int
    qualifying_position: int | None
    q1_time: float | None
    q2_time: float | None
    q3_time: float | None


class DataAgent:
    """Fetch and persist Formula 1 data using FastF1."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self._session_factory = session_factory or SessionLocal

    def fetch_season_schedule(self, year: int) -> list[Race]:
        """Download a season schedule and save race metadata."""

        schedule = self._load_event_schedule(year)
        if schedule.empty:
            LOGGER.warning("No schedule rows returned for season %s.", year)
            return []

        records = self._build_schedule_records(year, schedule)
        if not records:
            LOGGER.warning("No valid schedule rows found for season %s.", year)
            return []

        with self._session_factory() as session:
            persisted_races = [self._upsert_race(session, record) for record in records]
            session.commit()

        LOGGER.info("Persisted %s race rows for season %s.", len(persisted_races), year)
        return persisted_races

    def fetch_race_results(self, year: int) -> list[RaceResult]:
        """Download race results for a season and persist them."""

        schedule = self._load_event_schedule(year)
        if schedule.empty:
            LOGGER.warning("No schedule rows returned for season %s.", year)
            return []

        records = self._build_schedule_records(year, schedule)
        if not records:
            LOGGER.warning("No valid schedule rows found for season %s.", year)
            return []

        persisted_results: list[RaceResult] = []
        with self._session_factory() as session:
            for record in records:
                race = self._upsert_race(session, record)
                persisted_results.extend(self._load_and_persist_race_results(session, year, race, record.race_name))
                session.commit()

            session.commit()

        LOGGER.info("Persisted %s race results for season %s.", len(persisted_results), year)
        return persisted_results

    def fetch_qualifying_results(self, year: int) -> list[QualifyingResult]:
        """Download qualifying results for a season and persist them."""

        schedule = self._load_event_schedule(year)
        if schedule.empty:
            LOGGER.warning("No schedule rows returned for season %s.", year)
            return []

        records = self._build_schedule_records(year, schedule)
        if not records:
            LOGGER.warning("No valid schedule rows found for season %s.", year)
            return []

        persisted_results: list[QualifyingResult] = []
        with self._session_factory() as session:
            for record in records:
                race = self._upsert_race(session, record)
                persisted_results.extend(self._load_and_persist_qualifying_results(session, year, race, record.race_name))
                session.commit()

            session.commit()

        LOGGER.info("Persisted %s qualifying results for season %s.", len(persisted_results), year)
        return persisted_results

    def populate_historical_data(self, start_year: int, end_year: int) -> dict[int, list[RaceResult]]:
        """Populate race results for every season in the requested range."""

        historical_data: dict[int, list[RaceResult]] = {}
        for year in range(start_year, end_year + 1):
            LOGGER.info("Populating historical F1 results for %s.", year)
            historical_data[year] = self.fetch_race_results(year)

        return historical_data

    def populate_historical_qualifying_data(self, start_year: int, end_year: int) -> dict[int, list[QualifyingResult]]:
        """Populate qualifying results for every season in the requested range."""

        historical_data: dict[int, list[QualifyingResult]] = {}
        for year in range(start_year, end_year + 1):
            LOGGER.info("Populating historical F1 qualifying results for %s.", year)
            historical_data[year] = self.fetch_qualifying_results(year)

        return historical_data

    def _load_event_schedule(self, year: int) -> DataFrame:
        """Load the official FastF1 event schedule for a season."""

        try:
            return fastf1.get_event_schedule(year)
        except Exception as exc:  # pragma: no cover - external API/network failure
            LOGGER.exception("Failed to load event schedule for season %s.", year)
            LOGGER.debug("FastF1 error: %s", exc)
            return pd.DataFrame()

    def _build_schedule_records(self, year: int, schedule: DataFrame) -> list[RaceRecord]:
        """Convert a FastF1 schedule dataframe into normalized race records."""

        records: list[RaceRecord] = []
        for row in schedule.to_dict(orient="records"):
            round_number = self._to_int(row.get("RoundNumber"))
            event_date = self._to_date(row.get("EventDate"))
            race_name = self._to_str(row.get("EventName"))
            circuit_name = self._to_str(row.get("CircuitName")) or self._to_str(row.get("Location"))
            circuit_country = self._to_str(row.get("Country")) or "Unknown"
            circuit_location = self._to_str(row.get("Location")) or circuit_name or "Unknown"

            if round_number is None or round_number <= 0:
                continue
            if event_date is None:
                continue

            records.append(
                RaceRecord(
                    season=year,
                    round_number=round_number,
                    race_name=race_name or f"Round {round_number}",
                    race_date=event_date,
                    circuit_name=circuit_name or race_name or f"Round {round_number}",
                    circuit_country=circuit_country,
                    circuit_location=circuit_location,
                )
            )

        return records

    def _load_and_persist_race_results(
        self,
        session: Session,
        year: int,
        race: Race,
        race_name: str,
    ) -> list[RaceResult]:
        """Load a race session from FastF1 and persist its classified results."""

        try:
            race_session = fastf1.get_session(year, race.round_number, "R")
            race_session.load()
            results = getattr(race_session, "results", None)
            if results is None or results.empty:
                LOGGER.warning("No race results returned for %s %s.", year, race_name)
                return []

            persisted_results: list[RaceResult] = []
            for row in results.to_dict(orient="records"):
                result_record = self._build_result_record(session, race, row)
                if result_record is None:
                    continue

                persisted_results.append(self._upsert_race_result(session, result_record))

            LOGGER.info("Loaded %s driver results for %s %s.", len(persisted_results), year, race_name)
            return persisted_results
        except Exception as exc:  # pragma: no cover - external API/network failure
            LOGGER.warning("Failed to load race results for %s %s.", year, race_name)
            LOGGER.debug("FastF1 error: %s", exc)
            return []

    def _load_and_persist_qualifying_results(
        self,
        session: Session,
        year: int,
        race: Race,
        race_name: str,
    ) -> list[QualifyingResult]:
        """Load a qualifying session from FastF1 and persist its classified results."""

        try:
            qualifying_session = fastf1.get_session(year, race.round_number, "Q")
            qualifying_session.load()
            results = getattr(qualifying_session, "results", None)
            if results is None or results.empty:
                LOGGER.warning("No qualifying results returned for %s %s.", year, race_name)
                return []

            persisted_results: list[QualifyingResult] = []
            for row in results.to_dict(orient="records"):
                result_record = self._build_qualifying_result_record(session, race, row)
                if result_record is None:
                    continue

                persisted_results.append(self._upsert_qualifying_result(session, result_record))

            LOGGER.info("Loaded %s qualifying results for %s %s.", len(persisted_results), year, race_name)
            return persisted_results
        except Exception as exc:  # pragma: no cover - external API/network failure
            LOGGER.warning("Failed to load qualifying results for %s %s.", year, race_name)
            LOGGER.debug("FastF1 error: %s", exc)
            return []

    def _build_result_record(self, session: Session, race: Race, row: dict[str, Any]) -> RaceResultRecord | None:
        """Convert a FastF1 result row into a normalized race result record."""

        driver_code = self._to_str(row.get("Abbreviation")) or self._to_str(row.get("DriverNumber"))
        driver_name = self._to_str(row.get("FullName")) or self._to_str(row.get("Driver")) or driver_code
        constructor_name = self._to_str(row.get("TeamName")) or self._to_str(row.get("Team"))
        status = self._to_str(row.get("Status")) or "Unknown"

        if driver_name is None or constructor_name is None:
            LOGGER.warning("Skipping result row for race_id=%s because driver or constructor is missing.", race.id)
            return None

        driver = self._get_or_create_driver(
            session=session,
            driver_code=driver_code or driver_name,
            driver_name=driver_name,
            nationality=self._to_str(row.get("CountryCode")) or "Unknown",
        )
        constructor = self._get_or_create_constructor(session=session, constructor_name=constructor_name)

        return RaceResultRecord(
            race_id=race.id,
            driver_id=driver.id,
            constructor_id=constructor.id,
            grid_position=self._to_int(row.get("GridPosition")),
            finish_position=self._to_int(row.get("Position")),
            points=self._to_float(row.get("Points")),
            status=status,
        )

    def _build_qualifying_result_record(
        self,
        session: Session,
        race: Race,
        row: dict[str, Any],
    ) -> QualifyingResultRecord | None:
        """Convert a FastF1 qualifying row into a normalized result record."""

        driver_code = self._to_str(row.get("Abbreviation")) or self._to_str(row.get("DriverNumber"))
        driver_name = self._to_str(row.get("FullName")) or self._to_str(row.get("Driver")) or driver_code
        constructor_name = self._to_str(row.get("TeamName")) or self._to_str(row.get("Team"))

        if driver_name is None or constructor_name is None:
            LOGGER.warning(
                "Skipping qualifying row for race_id=%s because driver or constructor is missing.",
                race.id,
            )
            return None

        driver = self._get_or_create_driver(
            session=session,
            driver_code=driver_code or driver_name,
            driver_name=driver_name,
            nationality=self._to_str(row.get("CountryCode")) or "Unknown",
        )
        constructor = self._get_or_create_constructor(session=session, constructor_name=constructor_name)

        return QualifyingResultRecord(
            race_id=race.id,
            driver_id=driver.id,
            constructor_id=constructor.id,
            qualifying_position=self._to_int(row.get("Position")) or self._to_int(row.get("ClassifiedPosition")),
            q1_time=self._to_seconds(row.get("Q1")),
            q2_time=self._to_seconds(row.get("Q2")),
            q3_time=self._to_seconds(row.get("Q3")),
        )

    def _get_or_create_driver(self, session: Session, driver_code: str, driver_name: str, nationality: str) -> Driver:
        """Create a driver if it does not already exist."""

        existing_driver = session.scalars(select(Driver).where(Driver.driver_code == driver_code)).first()
        if existing_driver is not None:
            return existing_driver

        first_name, last_name = self._split_driver_name(driver_name)
        driver = Driver(
            driver_code=driver_code,
            first_name=first_name,
            last_name=last_name,
            nationality=nationality,
        )
        session.add(driver)
        session.flush()
        LOGGER.info("Created missing driver %s.", driver_name)
        return driver

    def _get_or_create_constructor(self, session: Session, constructor_name: str) -> Constructor:
        """Create a constructor if it does not already exist."""

        existing_constructor = session.scalars(select(Constructor).where(Constructor.name == constructor_name)).first()
        if existing_constructor is not None:
            return existing_constructor

        constructor = Constructor(name=constructor_name, nationality="Unknown")
        session.add(constructor)
        session.flush()
        LOGGER.info("Created missing constructor %s.", constructor_name)
        return constructor

    def _get_or_create_circuit(self, session: Session, record: RaceRecord) -> Circuit:
        """Create or update a circuit from schedule metadata."""

        existing_circuit = session.scalars(select(Circuit).where(Circuit.name == record.circuit_name)).first()
        if existing_circuit is not None:
            existing_circuit.country = record.circuit_country
            existing_circuit.location = record.circuit_location
            return existing_circuit

        circuit = Circuit(
            name=record.circuit_name,
            country=record.circuit_country,
            location=record.circuit_location,
        )
        session.add(circuit)
        session.flush()
        LOGGER.info("Created circuit %s.", record.circuit_name)
        return circuit

    def _upsert_race(self, session: Session, record: RaceRecord) -> Race:
        """Insert or update a race row based on season and round number."""

        circuit = self._get_or_create_circuit(session, record)

        existing_race = session.scalars(
            select(Race).where(
                Race.season == record.season,
                Race.round_number == record.round_number,
            )
        ).first()

        if existing_race is None:
            existing_race = Race(
                season=record.season,
                round_number=record.round_number,
                race_name=record.race_name,
                race_date=record.race_date,
                circuit_id=circuit.id,
            )
            session.add(existing_race)
            session.flush()
            LOGGER.info("Created race %s round %s.", record.season, record.round_number)
            return existing_race

        existing_race.race_name = record.race_name
        existing_race.race_date = record.race_date
        existing_race.circuit_id = circuit.id
        return existing_race

    def _upsert_race_result(self, session: Session, record: RaceResultRecord) -> RaceResult:
        """Insert or update a race result row while preventing duplicates."""

        existing_result = session.scalars(
            select(RaceResult).where(
                RaceResult.race_id == record.race_id,
                RaceResult.driver_id == record.driver_id,
            )
        ).first()

        if existing_result is None:
            existing_result = RaceResult(
                race_id=record.race_id,
                driver_id=record.driver_id,
                constructor_id=record.constructor_id,
                grid_position=record.grid_position,
                finish_position=record.finish_position,
                points=record.points,
                status=record.status,
            )
            session.add(existing_result)
            return existing_result

        existing_result.constructor_id = record.constructor_id
        existing_result.grid_position = record.grid_position
        existing_result.finish_position = record.finish_position
        existing_result.points = record.points
        existing_result.status = record.status
        return existing_result

    def _upsert_qualifying_result(
        self,
        session: Session,
        record: QualifyingResultRecord,
    ) -> QualifyingResult:
        """Insert or update a qualifying result while preventing duplicates."""

        existing_result = session.scalars(
            select(QualifyingResult).where(
                QualifyingResult.race_id == record.race_id,
                QualifyingResult.driver_id == record.driver_id,
            )
        ).first()

        if existing_result is None:
            existing_result = QualifyingResult(
                race_id=record.race_id,
                driver_id=record.driver_id,
                constructor_id=record.constructor_id,
                qualifying_position=record.qualifying_position,
                q1_time=record.q1_time,
                q2_time=record.q2_time,
                q3_time=record.q3_time,
            )
            session.add(existing_result)
            return existing_result

        existing_result.constructor_id = record.constructor_id
        existing_result.qualifying_position = record.qualifying_position
        existing_result.q1_time = record.q1_time
        existing_result.q2_time = record.q2_time
        existing_result.q3_time = record.q3_time
        return existing_result

    @staticmethod
    def _split_driver_name(driver_name: str) -> tuple[str, str]:
        """Split a full name into first and last name components."""

        parts = driver_name.split()
        if not parts:
            return "Unknown", "Driver"
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

    @staticmethod
    def _to_int(value: Any) -> int | None:
        """Convert a value into an integer when possible."""

        if value is None or pd.isna(value):
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """Convert a value into a float when possible."""

        if value is None or pd.isna(value):
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_seconds(value: Any) -> float | None:
        """Convert a FastF1 timing value into seconds when possible."""

        if value is None or pd.isna(value):
            return None

        if isinstance(value, pd.Timedelta):
            return value.total_seconds()

        if hasattr(value, "total_seconds"):
            return float(value.total_seconds())

        try:
            return float(value)
        except (TypeError, ValueError):
            pass

        try:
            return pd.to_timedelta(value).total_seconds()
        except (TypeError, ValueError):
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_str(value: Any) -> str | None:
        """Convert a value into a stripped string when possible."""

        if value is None or pd.isna(value):
            return None

        text = str(value).strip()
        return text or None

    @staticmethod
    def _to_date(value: Any) -> date | None:
        """Convert a FastF1 schedule value into a date object."""

        if value is None or pd.isna(value):
            return None

        return pd.to_datetime(value).date()


__all__ = ["DataAgent", "QualifyingResultRecord", "RaceRecord", "RaceResultRecord"]
