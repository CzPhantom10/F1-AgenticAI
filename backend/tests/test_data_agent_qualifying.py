"""Tests for DataAgent qualifying persistence."""

from __future__ import annotations

import unittest
from datetime import date

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.agents.data_agent import DataAgent, QualifyingResultRecord, RaceRecord
from app.database.base import Base
from app.models import Circuit, Constructor, Driver, QualifyingResult, Race, RaceResult


class DataAgentQualifyingTest(unittest.TestCase):
    """Unit tests for qualifying result upserts."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.agent = DataAgent(session_factory=self.session_factory)

    def test_upsert_qualifying_result_prevents_duplicates(self) -> None:
        with self.session_factory() as session:
            race = self.agent._upsert_race(
                session,
                RaceRecord(
                    season=2024,
                    round_number=1,
                    race_name="Bahrain Grand Prix",
                    race_date=date(2024, 3, 2),
                    circuit_name="Bahrain International Circuit",
                    circuit_country="Bahrain",
                    circuit_location="Sakhir",
                ),
            )
            driver = self.agent._get_or_create_driver(session, "VER", "Max Verstappen", "NED")
            constructor = self.agent._get_or_create_constructor(session, "Red Bull Racing")

            record = QualifyingResultRecord(
                race_id=race.id,
                driver_id=driver.id,
                constructor_id=constructor.id,
                qualifying_position=1,
                q1_time=90.123,
                q2_time=89.456,
                q3_time=88.789,
            )

            self.agent._upsert_qualifying_result(session, record)
            session.commit()

            self.agent._upsert_qualifying_result(
                session,
                QualifyingResultRecord(
                    race_id=race.id,
                    driver_id=driver.id,
                    constructor_id=constructor.id,
                    qualifying_position=2,
                    q1_time=91.0,
                    q2_time=90.0,
                    q3_time=89.0,
                ),
            )
            session.commit()

            results = session.scalars(select(QualifyingResult)).all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].qualifying_position, 2)
        self.assertEqual(results[0].q3_time, 89.0)

    def test_build_qualifying_record_converts_timedelta_columns(self) -> None:
        with self.session_factory() as session:
            race = self.agent._upsert_race(
                session,
                RaceRecord(
                    season=2024,
                    round_number=1,
                    race_name="Bahrain Grand Prix",
                    race_date=date(2024, 3, 2),
                    circuit_name="Bahrain International Circuit",
                    circuit_country="Bahrain",
                    circuit_location="Sakhir",
                ),
            )
            record = self.agent._build_qualifying_result_record(
                session,
                race,
                {
                    "Abbreviation": "LEC",
                    "FullName": "Charles Leclerc",
                    "TeamName": "Ferrari",
                    "CountryCode": "MON",
                    "Position": 1,
                    "Q1": pd.to_timedelta("0 days 00:01:30.123"),
                    "Q2": pd.to_timedelta("0 days 00:01:29.456"),
                    "Q3": pd.to_timedelta("0 days 00:01:28.789"),
                },
            )

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.qualifying_position, 1)
        self.assertAlmostEqual(record.q1_time or 0, 90.123)
        self.assertAlmostEqual(record.q2_time or 0, 89.456)
        self.assertAlmostEqual(record.q3_time or 0, 88.789)


if __name__ == "__main__":
    unittest.main()
