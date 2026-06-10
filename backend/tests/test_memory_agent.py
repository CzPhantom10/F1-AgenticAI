"""Integration and unit tests for the Memory Agent and endpoints."""

from __future__ import annotations

from datetime import date, datetime
import json
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models import Circuit, Constructor, Driver, QualifyingResult, Race, RaceResult
from app.models.memory import DriverInsight, ConstructorInsight, CircuitInsight
from app.agents.memory_agent import MemoryAgent


class MemoryAgentTest(unittest.TestCase):
    """Test MemoryAgent rebuild logic and FastAPI memory endpoints."""

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
            # 1. Circuit
            monaco = Circuit(name="Circuit de Monaco", country="Monaco", location="Monte Carlo")
            session.add(monaco)
            session.flush()

            # 2. Race
            monaco_race = Race(
                season=2024,
                round_number=8,
                race_name="Monaco Grand Prix",
                race_date=date(2024, 5, 26),
                circuit_id=monaco.id,
            )
            session.add(monaco_race)
            session.flush()

            # 3. Drivers & Constructors
            ver = Driver(driver_code="VER", first_name="Max", last_name="Verstappen", nationality="Dutch")
            ham = Driver(driver_code="HAM", first_name="Lewis", last_name="Hamilton", nationality="British")
            red_bull = Constructor(name="Red Bull Racing", nationality="Austrian")
            mercedes = Constructor(name="Mercedes", nationality="German")
            session.add_all([ver, ham, red_bull, mercedes])
            session.flush()

            # 4. Results
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
                        q1_time=70.1,
                        q2_time=69.8,
                        q3_time=69.4,
                    ),
                    QualifyingResult(
                        race_id=monaco_race.id,
                        driver_id=ham.id,
                        constructor_id=mercedes.id,
                        qualifying_position=2,
                        q1_time=70.3,
                        q2_time=70.0,
                        q3_time=69.6,
                    ),
                ]
            )
            session.commit()

    def test_rebuild_all_creates_insights(self) -> None:
        agent = MemoryAgent()
        with self.session_factory() as session:
            stats = agent.rebuild_all(session)
            self.assertTrue(stats.success)
            self.assertEqual(stats.drivers_processed, 2)
            self.assertEqual(stats.constructors_processed, 2)
            self.assertEqual(stats.circuits_processed, 1)

            # Retrieve insights
            driver_ins = agent.get_driver_insight(session, 1) # Max
            self.assertIsNotNone(driver_ins)
            self.assertEqual(driver_ins.total_wins, 1)
            self.assertEqual(driver_ins.total_points, 25.0)

            circuit_ins = agent.get_circuit_insight(session, 1) # Monaco
            self.assertIsNotNone(circuit_ins)
            winners = json.loads(circuit_ins.historical_winners_json)
            self.assertEqual(len(winners), 1)
            self.assertEqual(winners[0]["driver_name"], "Max Verstappen")

    def test_memory_endpoints(self) -> None:
        # Rebuild first via POST
        rebuild_resp = self.client.post("/memory/rebuild")
        self.assertEqual(rebuild_resp.status_code, 200)
        rebuild_data = rebuild_resp.json()
        self.assertTrue(rebuild_data["success"])
        self.assertEqual(rebuild_data["circuits_processed"], 1)

        # GET driver insight
        driver_resp = self.client.get("/memory/driver/1")
        self.assertEqual(driver_resp.status_code, 200)
        self.assertEqual(driver_resp.json()["total_wins"], 1)

        # GET constructor insight
        const_resp = self.client.get("/memory/constructor/1")
        self.assertEqual(const_resp.status_code, 200)
        self.assertEqual(const_resp.json()["total_wins"], 1)

        # GET circuit insight
        circ_resp = self.client.get("/memory/circuit/1")
        self.assertEqual(circ_resp.status_code, 200)
        self.assertIn("Verstappen", circ_resp.json()["historical_winners_json"])

        # Non-existent ID returns 404
        bad_resp = self.client.get("/memory/driver/999")
        self.assertEqual(bad_resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
