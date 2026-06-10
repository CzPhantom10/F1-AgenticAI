"""Integration tests for the FastAPI resource endpoints."""

from __future__ import annotations

from datetime import date

import unittest

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models import Circuit, Constructor, Driver, QualifyingResult, Race, RaceResult


class ApiRoutesTest(unittest.TestCase):
    """Exercise the newly created REST endpoints against an isolated SQLite database."""

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

        def override_get_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self._seed_data()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _seed_data(self) -> None:
        with self.session_factory() as session:
            circuit_one = Circuit(name="Bahrain International Circuit", country="Bahrain", location="Sakhir")
            circuit_two = Circuit(name="Jeddah Corniche Circuit", country="Saudi Arabia", location="Jeddah")
            session.add_all([circuit_one, circuit_two])
            session.flush()

            race_one = Race(
                season=2024,
                round_number=1,
                race_name="Bahrain Grand Prix",
                race_date=date(2024, 3, 2),
                circuit_id=circuit_one.id,
            )
            race_two = Race(
                season=2024,
                round_number=2,
                race_name="Saudi Arabian Grand Prix",
                race_date=date(2024, 3, 9),
                circuit_id=circuit_two.id,
            )
            session.add_all([race_one, race_two])
            session.flush()

            drivers = [
                Driver(driver_code="HAM", first_name="Lewis", last_name="Hamilton", nationality="British"),
                Driver(driver_code="LEC", first_name="Charles", last_name="Leclerc", nationality="Monegasque"),
                Driver(driver_code="VER", first_name="Max", last_name="Verstappen", nationality="Dutch"),
            ]
            constructors = [
                Constructor(name="Ferrari", nationality="Italian"),
                Constructor(name="Mercedes", nationality="German"),
            ]
            session.add_all(drivers + constructors)
            session.flush()

            session.add_all(
                [
                    RaceResult(
                        race_id=race_one.id,
                        driver_id=drivers[0].id,
                        constructor_id=constructors[1].id,
                        grid_position=1,
                        finish_position=1,
                        points=25.0,
                        status="Finished",
                    ),
                    RaceResult(
                        race_id=race_one.id,
                        driver_id=drivers[1].id,
                        constructor_id=constructors[0].id,
                        grid_position=2,
                        finish_position=2,
                        points=18.0,
                        status="Finished",
                    ),
                    RaceResult(
                        race_id=race_two.id,
                        driver_id=drivers[2].id,
                        constructor_id=constructors[1].id,
                        grid_position=1,
                        finish_position=1,
                        points=25.0,
                        status="Finished",
                    ),
                    RaceResult(
                        race_id=race_two.id,
                        driver_id=drivers[0].id,
                        constructor_id=constructors[1].id,
                        grid_position=2,
                        finish_position=2,
                        points=18.0,
                        status="Finished",
                    ),
                    QualifyingResult(
                        race_id=race_two.id,
                        driver_id=drivers[2].id,
                        constructor_id=constructors[1].id,
                        qualifying_position=1,
                        q1_time=90.123,
                        q2_time=89.456,
                        q3_time=88.789,
                    ),
                    QualifyingResult(
                        race_id=race_two.id,
                        driver_id=drivers[1].id,
                        constructor_id=constructors[0].id,
                        qualifying_position=2,
                        q1_time=90.5,
                        q2_time=89.8,
                        q3_time=89.0,
                    ),
                ]
            )
            session.commit()

            self.race_one_id = race_one.id
            self.race_two_id = race_two.id
            self.driver_ids = {driver.driver_code: driver.id for driver in drivers}
            self.constructor_ids = {constructor.name: constructor.id for constructor in constructors}

    def test_race_list_and_detail(self) -> None:
        response = self.client.get("/races?limit=1&offset=1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"]["total"], 2)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["race_name"], "Bahrain Grand Prix")
        self.assertEqual(payload["items"][0]["circuit"]["name"], "Bahrain International Circuit")

        response = self.client.get(f"/races/{self.race_one_id}")
        self.assertEqual(response.status_code, 200)
        race = response.json()
        self.assertEqual(race["race_name"], "Bahrain Grand Prix")
        self.assertEqual(race["circuit"]["country"], "Bahrain")

    def test_driver_and_constructor_endpoints(self) -> None:
        response = self.client.get("/drivers?limit=2&offset=1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"]["total"], 3)
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["items"][0]["driver_code"], "LEC")

        response = self.client.get(f"/drivers/{self.driver_ids['VER']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["driver"]["driver_code"], "VER")

        response = self.client.get("/constructors?limit=1&offset=0")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"]["total"], 2)
        self.assertEqual(payload["items"][0]["name"], "Ferrari")

        response = self.client.get(f"/constructors/{self.constructor_ids['Ferrari']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Ferrari")

    def test_latest_results_endpoints(self) -> None:
        response = self.client.get("/results/latest")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["race"]["race_name"], "Saudi Arabian Grand Prix")
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(payload["results"][0]["driver"]["driver_code"], "VER")

        response = self.client.get("/qualifying/latest")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["race"]["race_name"], "Saudi Arabian Grand Prix")
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(payload["results"][0]["driver"]["driver_code"], "VER")

    def test_standings_endpoints(self) -> None:
        response = self.client.get("/standings/drivers?limit=2")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"]["total"], 3)
        self.assertEqual(payload["items"][0]["driver"]["driver_code"], "HAM")
        self.assertEqual(payload["items"][0]["points"], 43.0)

        response = self.client.get("/standings/constructors?limit=2")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"]["total"], 2)
        self.assertEqual(payload["items"][0]["constructor"]["name"], "Mercedes")
        self.assertEqual(payload["items"][0]["points"], 68.0)

    def test_upcoming_race_endpoint(self) -> None:
        schedule = pd.DataFrame(
            [
                {
                    "Year": 2026,
                    "RoundNumber": 12,
                    "EventName": "Test Grand Prix",
                    "EventDate": pd.Timestamp(date.today().replace(year=date.today().year) + pd.Timedelta(days=14)),
                    "CircuitName": "Test Circuit",
                    "Country": "Testland",
                    "Location": "Test City",
                }
            ]
        )

        with patch("app.api.routes.resources.fastf1.get_event_schedule", return_value=schedule):
            response = self.client.get("/races/upcoming")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["race_name"], "Test Grand Prix")
        self.assertEqual(payload["circuit"]["name"], "Test Circuit")
        self.assertEqual(payload["days_until"], 14)

    def test_missing_item_returns_404(self) -> None:
        response = self.client.get("/drivers/999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Driver not found")


if __name__ == "__main__":
    unittest.main()