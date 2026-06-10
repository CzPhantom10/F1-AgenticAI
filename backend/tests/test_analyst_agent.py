"""Unit tests for Analyst Agent — v4 query classification + memory-based routing + retrieved source metadata."""

from __future__ import annotations

from datetime import date
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.analyst_agent import (
    AnalystAgent,
    AnalystConfigurationError,
    AnalystServiceError,
    QueryType,
)
from app.core.config import Settings
from app.database.base import Base
from app.models import Circuit, Constructor, Driver, QualifyingResult, Race, RaceResult


def _make_settings(**overrides) -> Settings:
    defaults = dict(
        app_name="Racecraft AI",
        app_version="1.0.0",
        environment="test",
        debug=False,
        database_url="sqlite:///:memory:",
        cors_origins=("http://localhost:5173",),
        groq_api_key="test-key",
        groq_model="llama-3.3-70b-versatile",
    )
    defaults.update(overrides)
    return Settings(**defaults)


class _BaseAnalystTest(unittest.TestCase):
    """Shared setup: in-memory SQLite with circuits, drivers, constructors, races."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self._seed_data()
        self.settings = _make_settings()
        self.agent = AnalystAgent(settings=self.settings)

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _seed_data(self) -> None:
        with self.session_factory() as session:
            monaco = Circuit(name="Circuit de Monaco", country="Monaco", location="Monte Carlo")
            silverstone = Circuit(name="Silverstone Circuit", country="United Kingdom", location="Silverstone")
            session.add_all([monaco, silverstone])
            session.flush()

            monaco_race = Race(
                season=2024, round_number=8, race_name="Monaco Grand Prix",
                race_date=date(2024, 5, 26), circuit_id=monaco.id,
            )
            silverstone_race = Race(
                season=2024, round_number=12, race_name="British Grand Prix",
                race_date=date(2024, 7, 7), circuit_id=silverstone.id,
            )
            session.add_all([monaco_race, silverstone_race])
            session.flush()

            ver = Driver(driver_code="VER", first_name="Max", last_name="Verstappen", nationality="Dutch")
            ham = Driver(driver_code="HAM", first_name="Lewis", last_name="Hamilton", nationality="British")
            red_bull = Constructor(name="Red Bull Racing", nationality="Austrian")
            mercedes = Constructor(name="Mercedes", nationality="German")
            session.add_all([ver, ham, red_bull, mercedes])
            session.flush()

            session.add_all([
                RaceResult(race_id=monaco_race.id, driver_id=ver.id, constructor_id=red_bull.id,
                           grid_position=1, finish_position=1, points=25.0, status="Finished"),
                RaceResult(race_id=monaco_race.id, driver_id=ham.id, constructor_id=mercedes.id,
                           grid_position=2, finish_position=2, points=18.0, status="Finished"),
                RaceResult(race_id=silverstone_race.id, driver_id=ham.id, constructor_id=mercedes.id,
                           grid_position=1, finish_position=1, points=25.0, status="Finished"),
                RaceResult(race_id=silverstone_race.id, driver_id=ver.id, constructor_id=red_bull.id,
                           grid_position=2, finish_position=2, points=18.0, status="Finished"),
            ])
            session.commit()


# ═════════════════════════════════════════════════════════════════════════════
#  QUERY CLASSIFICATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

class QueryClassificationTest(_BaseAnalystTest):
    """Test that _classify_query returns the correct QueryType intents."""

    def test_circuit_driver_ranking_detected(self) -> None:
        with self.session_factory() as session:
            drivers = self.agent._match_drivers(session, "Who performs best at Silverstone?")
            circuits = self.agent._match_circuits(session, "Who performs best at Silverstone?")
            constructors = self.agent._match_constructors(session, "Who performs best at Silverstone?")
        qt = AnalystAgent._classify_query("Who performs best at Silverstone?", drivers, circuits, constructors)
        self.assertEqual(qt, QueryType.CIRCUIT_DRIVER_RANKING)

    def test_circuit_constructor_ranking_detected(self) -> None:
        with self.session_factory() as session:
            drivers = self.agent._match_drivers(session, "Who is the best constructor at Monaco?")
            circuits = self.agent._match_circuits(session, "Who is the best constructor at Monaco?")
            constructors = self.agent._match_constructors(session, "Who is the best constructor at Monaco?")
        qt = AnalystAgent._classify_query("Who is the best constructor at Monaco?", drivers, circuits, constructors)
        self.assertEqual(qt, QueryType.CIRCUIT_CONSTRUCTOR_RANKING)

    def test_driver_comparison_detected(self) -> None:
        with self.session_factory() as session:
            drivers = self.agent._match_drivers(session, "Compare Lewis Hamilton and Max Verstappen career stats")
            circuits = self.agent._match_circuits(session, "Compare Lewis Hamilton and Max Verstappen career stats")
            constructors = self.agent._match_constructors(session, "Compare Lewis Hamilton and Max Verstappen career stats")
        qt = AnalystAgent._classify_query("Compare Lewis Hamilton and Max Verstappen career stats", drivers, circuits, constructors)
        self.assertEqual(qt, QueryType.DRIVER_COMPARISON)

    def test_season_summary_detected(self) -> None:
        with self.session_factory() as session:
            drivers = self.agent._match_drivers(session, "Who dominated 2024?")
            circuits = self.agent._match_circuits(session, "Who dominated 2024?")
            constructors = self.agent._match_constructors(session, "Who dominated 2024?")
        qt = AnalystAgent._classify_query("Who dominated 2024?", drivers, circuits, constructors)
        self.assertEqual(qt, QueryType.SEASON_SUMMARY)


# ═════════════════════════════════════════════════════════════════════════════
#  ROUTING AND RETRIEVED SOURCE SELECTION TESTS
# ═════════════════════════════════════════════════════════════════════════════

class IntentRoutingTest(_BaseAnalystTest):
    """Verify memory routing and that exact records are retrieved without mixing tables."""

    def test_compare_hamilton_vs_verstappen(self) -> None:
        with self.session_factory() as session:
            context, sources, meta = self.agent._build_context(session, "Compare Lewis Hamilton and Max Verstappen career stats")

        self.assertIn("Driver Comparison", context)
        self.assertEqual(sources[0].type, "driver_memory")
        self.assertIn("DATA SOURCE:\n- Driver Memory", meta)
        self.assertNotIn("Circuit Insight", meta)

    def test_best_constructor_at_monaco(self) -> None:
        with self.session_factory() as session:
            context, sources, meta = self.agent._build_context(session, "Who is the best constructor at Monaco?")

        self.assertIn("Constructor Performance Rankings", context)
        self.assertEqual(sources[0].type, "circuit_memory")
        self.assertIn("DATA SOURCE:\n- Circuit Memory", meta)
        self.assertIn("Best Constructors", meta)
        self.assertNotIn("Best Drivers", meta)

    def test_best_driver_at_silverstone(self) -> None:
        with self.session_factory() as session:
            context, sources, meta = self.agent._build_context(session, "Who performs best at Silverstone?")

        self.assertIn("Driver Performance Rankings", context)
        self.assertEqual(sources[0].type, "circuit_memory")
        self.assertIn("DATA SOURCE:\n- Circuit Memory", meta)
        self.assertIn("Best Drivers", meta)
        self.assertNotIn("Best Constructors", meta)

    def test_who_dominated_2024(self) -> None:
        with self.session_factory() as session:
            context, sources, meta = self.agent._build_context(session, "Who dominated 2024?")

        self.assertIn("Season Summary: 2024", context)
        self.assertEqual(sources[0].type, "season_memory")
        self.assertIn("DATA SOURCE:\n- Season Memory", meta)


# ═════════════════════════════════════════════════════════════════════════════
#  GROQ INTEGRATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

class GroqIntegrationTest(_BaseAnalystTest):
    """Verify Groq error handling."""

    def test_answer_requires_groq_configuration(self) -> None:
        agent = AnalystAgent(settings=_make_settings(groq_api_key=None))
        with self.session_factory() as session:
            with self.assertRaises(AnalystConfigurationError):
                agent.answer(session, "Who won at Monaco 2024?")

    def test_answer_surfaces_groq_failures(self) -> None:
        class BrokenGroq:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        raise RuntimeError("network down")

        agent = AnalystAgent(settings=self.settings, groq_client=BrokenGroq())
        with self.session_factory() as session:
            with self.assertRaises(AnalystServiceError):
                agent.answer(session, "Who won at Monaco 2024?")

class RegressionIntentRoutingTest(_BaseAnalystTest):
    """Regression tests to verify correct intent routing for Phase 3 cleanup queries."""

    def test_regression_intents(self) -> None:
        queries = [
            ("Compare Leclerc and Norris career stats", QueryType.DRIVER_COMPARISON),
            ("Compare Hamilton and Verstappen career stats", QueryType.DRIVER_COMPARISON),
            ("Show Norris career summary", QueryType.DRIVER_STATS),
            ("Show Leclerc career summary", QueryType.DRIVER_STATS),
            ("Compare Ferrari and Mercedes at Monaco", QueryType.CIRCUIT_CONSTRUCTOR_RANKING),
            ("Which constructor performs best at Silverstone?", QueryType.CIRCUIT_CONSTRUCTOR_RANKING),
            ("Who performs best at Monaco?", QueryType.CIRCUIT_DRIVER_RANKING),
            ("Predict winner of Monaco GP", QueryType.RACE_PREDICTION),
        ]
        with self.session_factory() as session:
            # Seed extra drivers Leclerc, Norris and constructors Ferrari, Mercedes to ensure matching succeeds in the test database
            lec = Driver(driver_code="LEC", first_name="Charles", last_name="Leclerc", nationality="Monegasque")
            nor = Driver(driver_code="NOR", first_name="Lando", last_name="Norris", nationality="British")
            ferrari = Constructor(name="Ferrari", nationality="Italian")
            session.add_all([lec, nor, ferrari])
            session.flush()

            for q, expected_qt in queries:
                drivers = self.agent._match_drivers(session, q)
                circuits = self.agent._match_circuits(session, q)
                constructors = self.agent._match_constructors(session, q)
                qt = self.agent._classify_query(q, drivers, circuits, constructors)
                self.assertEqual(qt, expected_qt, f"Query '{q}' classified as {qt} instead of {expected_qt}")


if __name__ == "__main__":
    unittest.main()
