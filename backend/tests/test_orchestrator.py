"""Unit tests for Orchestrator Agent."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.orchestrator_agent import OrchestratorAgent
from app.core.config import Settings
from app.database.base import Base
from app.models import Circuit, Constructor, Driver, Race, RaceResult


def _make_settings(**overrides) -> Settings:
    defaults = dict(
        app_name="Racecraft AI",
        app_version="1.0.0",
        environment="test",
        debug=False,
        database_url="sqlite:///:memory:",
        cors_origins=("http://localhost:5173",),
        groq_api_key="mock-groq-key",
        groq_model="llama-3.3-70b-versatile",
    )
    defaults.update(overrides)
    return Settings(**defaults)


class TestOrchestratorAgent(unittest.TestCase):
    """Test suite for the Orchestrator Agent planning and routing."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self._seed_data()
        self.settings = _make_settings()
        self.agent = OrchestratorAgent(settings=self.settings)

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _seed_data(self) -> None:
        with self.session_factory() as session:
            monaco = Circuit(name="Circuit de Monaco", country="Monaco", location="Monte Carlo")
            silverstone = Circuit(name="Silverstone Circuit", country="United Kingdom", location="Silverstone")
            session.add_all([monaco, silverstone])
            session.flush()

            hamilton = Driver(driver_code="HAM", first_name="Lewis", last_name="Hamilton", nationality="British")
            verstappen = Driver(driver_code="VER", first_name="Max", last_name="Verstappen", nationality="Dutch")
            norris = Driver(driver_code="NOR", first_name="Lando", last_name="Norris", nationality="British")
            session.add_all([hamilton, verstappen, norris])
            session.flush()

            ferrari = Constructor(name="Ferrari", nationality="Italian")
            mercedes = Constructor(name="Mercedes", nationality="German")
            session.add_all([ferrari, mercedes])
            session.flush()

            race = Race(
                season=2026,
                round_number=1,
                race_name="Monaco Grand Prix",
                race_date=date(2026, 5, 24),
                circuit_id=monaco.id,
            )
            session.add(race)
            session.flush()

            # Add race results so prediction agent doesn't crash on empty DB
            res1 = RaceResult(
                race_id=race.id,
                driver_id=hamilton.id,
                constructor_id=mercedes.id,
                grid_position=1,
                finish_position=1,
                points=25.0,
                status="Finished",
            )
            res2 = RaceResult(
                race_id=race.id,
                driver_id=verstappen.id,
                constructor_id=ferrari.id,
                grid_position=2,
                finish_position=2,
                points=18.0,
                status="Finished",
            )
            session.add_all([res1, res2])
            session.commit()

    def test_query_planning_circuit(self) -> None:
        with self.session_factory() as session:
            circuits = self.agent._analyst_agent._match_circuits(session, "Who performs best at Silverstone?")
            plan = self.agent.plan_query("Who performs best at Silverstone?", [], circuits, [])
            self.assertIn("CircuitMemory", plan)
            self.assertNotIn("DriverMemory", plan)

    def test_query_planning_comparison(self) -> None:
        with self.session_factory() as session:
            drivers = self.agent._analyst_agent._match_drivers(session, "Compare Hamilton and Verstappen career stats")
            plan = self.agent.plan_query("Compare Hamilton and Verstappen career stats", drivers, [], [])
            self.assertIn("DriverMemory", plan)
            self.assertIn("HistoricalStats", plan)

    def test_query_planning_prediction(self) -> None:
        with self.session_factory() as session:
            circuits = self.agent._analyst_agent._match_circuits(session, "Predict the Silverstone GP podium")
            plan = self.agent.plan_query("Predict the Silverstone GP podium", [], circuits, [])
            self.assertIn("CircuitMemory", plan)
            self.assertIn("DriverMemory", plan)
            self.assertIn("PredictionAgent", plan)

    def test_query_planning_prediction_drivers(self) -> None:
        with self.session_factory() as session:
            drivers = self.agent._analyst_agent._match_drivers(session, "Will Norris beat Verstappen at Monaco?")
            circuits = self.agent._analyst_agent._match_circuits(session, "Will Norris beat Verstappen at Monaco?")
            plan = self.agent.plan_query("Will Norris beat Verstappen at Monaco?", drivers, circuits, [])
            self.assertIn("CircuitMemory", plan)
            self.assertIn("DriverMemory", plan)
            self.assertIn("PredictionAgent", plan)

    def test_query_planning_multi_tool(self) -> None:
        with self.session_factory() as session:
            circuits = self.agent._analyst_agent._match_circuits(session, "Compare Ferrari and Mercedes at Monaco")
            constructors = self.agent._analyst_agent._match_constructors(session, "Compare Ferrari and Mercedes at Monaco")
            plan = self.agent.plan_query("Compare Ferrari and Mercedes at Monaco", [], circuits, constructors)
            self.assertIn("CircuitMemory", plan)
            self.assertIn("ConstructorMemory", plan)

    @patch("app.agents.orchestrator_agent.Groq")
    def test_context_inheritance(self, mock_groq_class: MagicMock) -> None:
        # Mock Groq response
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Answer\nWinner predicted\n\nKey Evidence\n• Hamilton\n\nWhy\nHamilton\n\nConfidence: High"
        mock_groq.chat.completions.create.return_value = mock_completion

        with self.session_factory() as session:
            history = [
                {"role": "user", "content": "Compare Hamilton and Verstappen career stats"},
                {"role": "assistant", "content": "Here is the comparison..."},
            ]
            # When asking a follow up query without names, it should inherit drivers from history
            result = self.agent.answer(session, "What about Silverstone?", history=history)
            self.assertIsNotNone(result)
            mock_groq.chat.completions.create.assert_called_once()
            # Assert "Silverstone" and matched drivers HAM, VER were loaded into context
            call_kwargs = mock_groq.chat.completions.create.call_args[1]
            user_msg = call_kwargs["messages"][1]["content"]
            self.assertIn("driver_memory", user_msg)
            self.assertIn("circuit_memory", user_msg)


from fastapi.testclient import TestClient
from app.main import app
from app.database.session import get_db
from sqlalchemy.pool import StaticPool

class TestOrchestratorRoutes(unittest.TestCase):
    """Exercise POST /orchestrator/query against an isolated database."""

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
            monaco = Circuit(name="Circuit de Monaco", country="Monaco", location="Monte Carlo")
            session.add(monaco)
            session.flush()

            hamilton = Driver(driver_code="HAM", first_name="Lewis", last_name="Hamilton", nationality="British")
            session.add(hamilton)
            session.flush()

            race = Race(
                season=2026,
                round_number=1,
                race_name="Monaco Grand Prix",
                race_date=date(2026, 5, 24),
                circuit_id=monaco.id,
            )
            session.add(race)
            session.flush()
            session.commit()

    @patch("app.agents.orchestrator_agent.Groq")
    def test_orchestrator_query_route(self, mock_groq_class: MagicMock) -> None:
        # Mock Groq response
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Answer\nWinner predicted\n\nKey Evidence\n• Hamilton\n\nWhy\nHamilton\n\nConfidence: High"
        mock_groq.chat.completions.create.return_value = mock_completion

        payload = {
            "question": "Compare Hamilton career stats",
            "history": []
        }
        response = self.client.post("/orchestrator/query", json=payload)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertIn("answer", json_data)
        self.assertIn("sources", json_data)

