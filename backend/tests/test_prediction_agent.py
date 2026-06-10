"""Unit and integration tests for the Prediction Agent and endpoints."""

from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models import Circuit, Constructor, Driver, QualifyingResult, Race, RaceResult
from app.agents.prediction_agent import PredictionAgent


class PredictionAgentTest(unittest.TestCase):
    """Test PredictionAgent composite scoring and prediction endpoints."""

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
            # Circuit & Race
            monaco = Circuit(name="Circuit de Monaco", country="Monaco", location="Monte Carlo")
            session.add(monaco)
            session.flush()

            monaco_race = Race(
                season=2024,
                round_number=8,
                race_name="Monaco Grand Prix",
                race_date=date(2024, 5, 26),
                circuit_id=monaco.id,
            )
            session.add(monaco_race)
            session.flush()

            # Drivers & Constructors
            ver = Driver(driver_code="VER", first_name="Max", last_name="Verstappen", nationality="Dutch")
            ham = Driver(driver_code="HAM", first_name="Lewis", last_name="Hamilton", nationality="British")
            red_bull = Constructor(name="Red Bull Racing", nationality="Austrian")
            mercedes = Constructor(name="Mercedes", nationality="German")
            session.add_all([ver, ham, red_bull, mercedes])
            session.flush()

            # Results
            session.add_all(
                [
                    RaceResult(
                        race_id=monaco_race.id,
                        driver_id=ver.id,
                        constructor_id=red_bull.id,
                        grid_position=1,
                        finish_position=1,
                        points=25.0,
                        status="Finished",
                    ),
                    RaceResult(
                        race_id=monaco_race.id,
                        driver_id=ham.id,
                        constructor_id=mercedes.id,
                        grid_position=2,
                        finish_position=2,
                        points=18.0,
                        status="Finished",
                    ),
                    QualifyingResult(
                        race_id=monaco_race.id,
                        driver_id=ver.id,
                        constructor_id=red_bull.id,
                        qualifying_position=1,
                    ),
                    QualifyingResult(
                        race_id=monaco_race.id,
                        driver_id=ham.id,
                        constructor_id=mercedes.id,
                        qualifying_position=2,
                    ),
                ]
            )
            session.commit()

    def test_predict_race_returns_top_predictions(self) -> None:
        agent = PredictionAgent()
        with self.session_factory() as session:
            resp = agent.predict_race(session, 1)
            # Max Verstappen is P1 in race result and qualifying -> should be predicted winner
            self.assertEqual(resp.winner.driver_code, "VER")
            self.assertEqual(len(resp.podium), 2)
            self.assertEqual(resp.podium[0].driver_code, "VER")
            self.assertEqual(resp.podium[1].driver_code, "HAM")
            self.assertGreater(resp.confidence_score, 50.0)

    def test_predict_race_endpoint(self) -> None:
        # Rebuild memory first
        self.client.post("/memory/rebuild")

        # Test predict endpoint
        resp = self.client.post("/predict/race/1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["winner"]["driver_code"], "VER")
        self.assertEqual(data["podium"][0]["driver_code"], "VER")
        self.assertIn("Winner predicted", data["evidence"][0])

        # Test non-existent race
        bad_resp = self.client.post("/predict/race/999")
        self.assertEqual(bad_resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
