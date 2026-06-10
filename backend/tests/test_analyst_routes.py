"""Integration tests for the Analyst Agent API."""

from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.analyst_agent import AnalystAgent, AnalystConfigurationError, AnalystDataError, AnalystServiceError
from app.core.config import Settings, get_settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models import Circuit, Constructor, Driver, QualifyingResult, Race, RaceResult


class AnalystRoutesTest(unittest.TestCase):
    """Exercise POST /analyst/query against an isolated SQLite database."""

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

        self.test_settings = Settings(
            app_name="Racecraft AI",
            app_version="1.0.0",
            environment="test",
            debug=False,
            database_url="sqlite://",
            cors_origins=("http://localhost:5173",),
            groq_api_key="test-key",
            groq_model="llama-3.3-70b-versatile",
        )
        get_settings.cache_clear()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _seed_data(self) -> None:
        with self.session_factory() as session:
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

            ver = Driver(driver_code="VER", first_name="Max", last_name="Verstappen", nationality="Dutch")
            red_bull = Constructor(name="Red Bull Racing", nationality="Austrian")
            session.add_all([ver, red_bull])
            session.flush()

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
                    QualifyingResult(
                        race_id=monaco_race.id,
                        driver_id=ver.id,
                        constructor_id=red_bull.id,
                        qualifying_position=1,
                        q1_time=70.1,
                        q2_time=69.8,
                        q3_time=69.4,
                    ),
                ]
            )
            session.commit()

    def _mock_groq_response(self, content: str) -> MagicMock:
        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content=content))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion
        return mock_client

    @patch("app.api.routes.analyst.AnalystAgent")
    def test_analyst_query_success(self, mock_agent_cls: MagicMock) -> None:
        mock_agent = mock_agent_cls.return_value
        mock_agent.answer.return_value = MagicMock(
            answer="Verstappen has won Monaco with pole and strong qualifying pace.",
            sources=[
                MagicMock(type="race_result", label="Monaco Grand Prix: Max Verstappen P1 (25.0 pts)"),
                MagicMock(type="qualifying_result", label="Monaco Grand Prix qualifying: Max Verstappen P1"),
            ],
        )

        response = self.client.post(
            "/analyst/query",
            json={"question": "Why is Verstappen strong at Monaco?"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("Verstappen", payload["answer"])
        self.assertEqual(len(payload["sources"]), 2)
        self.assertEqual(payload["sources"][0]["type"], "race_result")
        mock_agent.answer.assert_called_once()

    def test_analyst_query_empty_question_returns_422(self) -> None:
        response = self.client.post("/analyst/query", json={"question": "   "})
        self.assertEqual(response.status_code, 422)

    @patch("app.api.routes.analyst.AnalystAgent")
    def test_analyst_query_missing_data_returns_404(self, mock_agent_cls: MagicMock) -> None:
        mock_agent_cls.return_value.answer.side_effect = AnalystDataError(
            "No relevant F1 data found for this question"
        )

        response = self.client.post(
            "/analyst/query",
            json={"question": "Why is Verstappen strong at Monaco?"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "No relevant F1 data found for this question")

    @patch("app.api.routes.analyst.AnalystAgent")
    def test_analyst_query_missing_groq_key_returns_503(self, mock_agent_cls: MagicMock) -> None:
        mock_agent_cls.return_value.answer.side_effect = AnalystConfigurationError(
            "Groq API key is not configured"
        )

        response = self.client.post(
            "/analyst/query",
            json={"question": "Why is Verstappen strong at Monaco?"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Groq API key is not configured")

    @patch("app.api.routes.analyst.AnalystAgent")
    def test_analyst_query_groq_failure_returns_502(self, mock_agent_cls: MagicMock) -> None:
        mock_agent_cls.return_value.answer.side_effect = AnalystServiceError(
            "Analyst service is temporarily unavailable"
        )

        response = self.client.post(
            "/analyst/query",
            json={"question": "Why is Verstappen strong at Monaco?"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Analyst service is temporarily unavailable")

    @patch("app.agents.analyst_agent.get_settings")
    def test_analyst_query_end_to_end_with_mocked_groq(self, mock_get_settings: MagicMock) -> None:
        mock_get_settings.return_value = self.test_settings
        agent = AnalystAgent(settings=self.test_settings, groq_client=self._mock_groq_response(
            "Verstappen converted pole into victory at Monaco in 2024."
        ))

        with patch("app.api.routes.analyst.AnalystAgent", return_value=agent):
            response = self.client.post(
                "/analyst/query",
                json={"question": "Why is Verstappen strong at Monaco?"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("Monaco", payload["answer"])
        self.assertGreaterEqual(len(payload["sources"]), 1)


if __name__ == "__main__":
    unittest.main()
