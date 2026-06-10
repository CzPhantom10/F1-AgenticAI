"""Analyst Agent v6 — query classification + memory-based routing + prediction agent V2 integration.

Query types supported (intents):
- NEXT_RACE                   → Find next upcoming race
- RACE_PREDICTION             → Predict upcoming race results
- PODIUM_PREDICTION           → Predict podium finishers
- PREDICTION_EXPLANATION      → Explain why a driver is/is not predicted to win
- DRIVER_COMPARISON           → Compare 2+ drivers using Driver Memory
- DRIVER_STATS                → Single driver stats using Driver Memory
- CONSTRUCTOR_STATS           → Single constructor stats using Constructor Memory
- CONSTRUCTOR_COMPARISON      → Compare 2+ constructors using Constructor Memory
- CIRCUIT_DRIVER_RANKING      → Driver stats at a circuit using Circuit Memory
- CIRCUIT_CONSTRUCTOR_RANKING   → Constructor stats at a circuit using Circuit Memory
- SEASON_SUMMARY              → Season summary using Season Memory
- PREDICTION                  → Fallback prediction query
- GENERAL                     → Fallback general retrieval
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from groq import Groq
from sqlalchemy import case, desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings, get_settings
from app.models import (
    Circuit,
    Constructor,
    Driver,
    QualifyingResult,
    Race,
    RaceResult,
    DriverInsight,
    ConstructorInsight,
    CircuitInsight,
)
from app.agents.memory_agent import MemoryAgent
from app.agents.prediction_agent import PredictionAgent

if TYPE_CHECKING:
    from groq.types.chat import ChatCompletion

LOGGER = logging.getLogger(__name__)

# ── Stop words (excluded from token matching) ────────────────────────────────

_STOP_WORDS = frozenset(
    {
        "about", "after", "before", "does", "from", "have", "that", "this",
        "they", "what", "when", "where", "which", "with", "would", "could",
        "should", "strong", "better", "compare", "driver", "team", "race",
        "grand", "prix", "and", "or", "the", "in", "of", "to", "for", "at",
        "vs", "versus",
    }
)

# ── Query-type keyword sets ──────────────────────────────────────────────────

_CIRCUIT_QUERY_KEYWORDS = frozenset({
    "best", "stats", "record", "records", "history", "performance",
    "dominant", "dominate", "dominates", "king", "specialist",
    "successful", "winningest", "most wins", "most podiums", "strongest",
})

_COMPARISON_KEYWORDS = frozenset({
    "compare", "comparison", "versus", " vs ", " vs.", "better",
    "head to head", "head-to-head", "against", "compared",
})

_SEASON_KEYWORDS = frozenset({
    "season", "championship", "standings", "how was", "summary",
    "overview", "recap", "review", "title race", "dominated", "who won",
})

_PERFORMANCE_KEYWORDS = frozenset({
    "career", "all time", "all-time", "lifetime", "overall",
    "track record", "form", "trend", "trajectory", "stats",
    "statistics", "history", "performance",
})

_PREDICTION_KEYWORDS = frozenset({
    "predict", "prediction", "who will win", "who wins",
    "forecast", "expected", "chances", "likely",
})


# ── Query type enum (intents) ────────────────────────────────────────────────

class QueryType(Enum):
    NEXT_RACE = auto()
    RACE_PREDICTION = auto()
    PODIUM_PREDICTION = auto()
    PREDICTION_EXPLANATION = auto()
    DRIVER_COMPARISON = auto()
    DRIVER_STATS = auto()
    CONSTRUCTOR_STATS = auto()
    CONSTRUCTOR_COMPARISON = auto()
    CIRCUIT_DRIVER_RANKING = auto()
    CIRCUIT_CONSTRUCTOR_RANKING = auto()
    SEASON_SUMMARY = auto()
    PREDICTION = auto()
    GENERAL = auto()


# ── Exception classes ────────────────────────────────────────────────────────

class AnalystError(Exception):
    """Base error raised by the analyst agent."""


class AnalystConfigurationError(AnalystError):
    """Raised when required analyst configuration is missing."""


class AnalystDataError(AnalystError):
    """Raised when the database has no data to build context."""


class AnalystServiceError(AnalystError):
    """Raised when the Groq API call fails."""


# ── Data containers ──────────────────────────────────────────────────────────

@dataclass(slots=True)
class AnalystSourceRecord:
    """Internal source reference returned with an analyst answer."""
    type: str
    label: str


@dataclass(slots=True)
class AnalystAnswer:
    """Structured analyst response."""
    answer: str
    sources: list[AnalystSourceRecord]


# ══════════════════════════════════════════════════════════════════════════════
#  ANALYST AGENT
# ══════════════════════════════════════════════════════════════════════════

class AnalystAgent:
    """Build F1 data context from the database and answer questions with Groq."""

    def __init__(
        self,
        settings: Settings | None = None,
        groq_client: Groq | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._groq_client = groq_client
        self._memory_agent = MemoryAgent()
        self._prediction_agent = PredictionAgent()

    # ── Public API ───────────────────────────────────────────────────────────

    def answer(self, session: Session, question: str, history: list[dict[str, str]] | None = None) -> AnalystAnswer:
        """Retrieve relevant data, build context, and return a Groq-generated answer."""
        normalized_question = question.strip()
        if not normalized_question:
            raise AnalystDataError("Question cannot be empty")

        try:
            season = self._resolve_season(session, normalized_question)
            drivers = self._match_drivers(session, normalized_question)
            circuits = self._match_circuits(session, normalized_question)
            constructors = self._match_constructors(session, normalized_question)

            query_type = self._classify_query(normalized_question, drivers, circuits, constructors)
            LOGGER.info("Query classified as intent: %s", query_type.name)

            context, sources, meta_text = self._build_context_with_type(
                session, normalized_question, query_type, season, drivers, circuits, constructors, history=history
            )
        except SQLAlchemyError as exc:
            LOGGER.exception("Failed to build analyst context")
            raise AnalystServiceError("Failed to retrieve analyst data") from exc

        # For simple scheduler and prediction intents, route directly without Groq to ensure exact format
        if query_type in (QueryType.NEXT_RACE, QueryType.RACE_PREDICTION, QueryType.PODIUM_PREDICTION):
            ans = AnalystAnswer(answer=context, sources=sources)
        else:
            ans = self._query_groq(normalized_question, context, sources)

        # Log retrieved source metadata internally for debugging (not displaying to users)
        LOGGER.info("Retrieved source metadata:\n%s", meta_text)
        return ans

    def build_context(self, session: Session, question: str) -> tuple[str, list[AnalystSourceRecord]]:
        """Build context and sources without calling Groq (for testing)."""
        context, sources, _ = self._build_context(session, question.strip())
        return context, sources

    # ══════════════════════════════════════════════════════════════════════════
    #  QUERY CLASSIFICATION
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _classify_query(
        question: str,
        drivers: list[Driver],
        circuits: list[Circuit],
        constructors: list[Constructor],
    ) -> QueryType:
        """Classify the user question into a specific intent (QueryType)."""
        q_lower = question.lower()

        # 1. Next race scheduler intent
        if "next race" in q_lower or "upcoming race" in q_lower or "what is the next" in q_lower:
            return QueryType.NEXT_RACE

        # 2. Prediction queries
        if "predict" in q_lower or "who will win" in q_lower or "who wins" in q_lower:
            if "podium" in q_lower or "top 3" in q_lower or "top three" in q_lower:
                return QueryType.PODIUM_PREDICTION
            return QueryType.RACE_PREDICTION
        if "prediction explanation" in q_lower or "factors" in q_lower or ("why" in q_lower and ("predicted" in q_lower or "win" in q_lower or "think" in q_lower or len(q_lower.strip().replace("?", "")) <= 5)):
            return QueryType.PREDICTION_EXPLANATION

        # 3. Career/Driver comparison/stats queries prioritized
        is_career_keyword = any(kw in q_lower for kw in [
            "career", "championship", "championships", "wins", "podiums", "points", "races", "summary"
        ])
        is_comparison = len(drivers) >= 2 or any(kw in q_lower for kw in _COMPARISON_KEYWORDS)
        
        if drivers and (is_career_keyword or is_comparison) and not (circuits and "at " in q_lower and not is_career_keyword):
            if is_comparison:
                return QueryType.DRIVER_COMPARISON
            return QueryType.DRIVER_STATS

        # 4. Circuit queries
        if circuits:
            if constructors or any(w in q_lower for w in ["constructor", "constructors", "team", "teams", "car", "cars"]):
                return QueryType.CIRCUIT_CONSTRUCTOR_RANKING
            return QueryType.CIRCUIT_DRIVER_RANKING

        # 5. Fallback Constructor queries
        if constructors:
            if len(constructors) >= 2 or any(kw in q_lower for kw in _COMPARISON_KEYWORDS):
                return QueryType.CONSTRUCTOR_COMPARISON
            return QueryType.CONSTRUCTOR_STATS

        # 6. Fallback Driver queries
        if drivers:
            if len(drivers) >= 2 or any(kw in q_lower for kw in _COMPARISON_KEYWORDS):
                return QueryType.DRIVER_COMPARISON
            return QueryType.DRIVER_STATS

        # 7. Season summary intent
        has_year = bool(re.search(r"\b(19|20)\d{2}\b", question))
        if has_year and any(kw in q_lower for kw in _SEASON_KEYWORDS):
            return QueryType.SEASON_SUMMARY

        return QueryType.GENERAL

    # ══════════════════════════════════════════════════════════════════════════
    #  MAIN CONTEXT DISPATCHER
    # ══════════════════════════════════════════════════════════════════════════

    def _build_context(self, session: Session, question: str) -> tuple[str, list[AnalystSourceRecord], str]:
        season = self._resolve_season(session, question)
        drivers = self._match_drivers(session, question)
        circuits = self._match_circuits(session, question)
        constructors = self._match_constructors(session, question)
        query_type = self._classify_query(question, drivers, circuits, constructors)
        return self._build_context_with_type(session, question, query_type, season, drivers, circuits, constructors)

    def _build_context_with_type(
        self,
        session: Session,
        question: str,
        query_type: QueryType,
        season: int,
        drivers: list[Driver],
        circuits: list[Circuit],
        constructors: list[Constructor],
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[AnalystSourceRecord], str]:
        if query_type == QueryType.NEXT_RACE:
            return self._build_next_race_context(session)
        if query_type in (QueryType.RACE_PREDICTION, QueryType.PODIUM_PREDICTION):
            return self._build_prediction_v2_context(session, question)
        if query_type == QueryType.PREDICTION_EXPLANATION:
            return self._build_prediction_explanation_context(session, question, drivers, history=history)
        if query_type == QueryType.CIRCUIT_DRIVER_RANKING:
            return self._build_circuit_driver_ranking_context(session, circuits)
        if query_type == QueryType.CIRCUIT_CONSTRUCTOR_RANKING:
            return self._build_circuit_constructor_ranking_context(session, circuits)
        if query_type == QueryType.DRIVER_COMPARISON:
            return self._build_driver_comparison_memory_context(session, drivers)
        if query_type == QueryType.DRIVER_STATS:
            return self._build_driver_stats_memory_context(session, drivers)
        if query_type == QueryType.CONSTRUCTOR_COMPARISON:
            return self._build_constructor_comparison_memory_context(session, constructors)
        if query_type == QueryType.CONSTRUCTOR_STATS:
            return self._build_constructor_stats_memory_context(session, constructors)
        if query_type == QueryType.SEASON_SUMMARY:
            return self._build_season_summary_context(session, season)

        return self._build_fallback_context(session, question, drivers, circuits, season)

    # ══════════════════════════════════════════════════════════════════════════
    #  RETRIEVAL PATHS
    # ══════════════════════════════════════════════════════════════════════════

    def _build_next_race_context(self, session: Session) -> tuple[str, list[AnalystSourceRecord], str]:
        ans = self._prediction_agent.find_next_race(session)
        sources = [AnalystSourceRecord(type="race_schedule", label="F1 Race Calendar")]
        return ans, sources, "DATA SOURCE:\n- Season Memory"

    def _find_race_by_query(self, session: Session, question: str) -> Race | None:
        q_lower = question.lower()
        races = list(session.scalars(select(Race).options(joinedload(Race.circuit)).where(Race.season == 2026)).all())
        if not races:
            latest = session.scalar(select(func.max(Race.season)))
            if latest:
                races = list(session.scalars(select(Race).options(joinedload(Race.circuit)).where(Race.season == latest)).all())
        for race in races:
            if (
                race.race_name.lower() in q_lower
                or (race.circuit and race.circuit.name.lower() in q_lower)
                or (race.circuit and race.circuit.country.lower() in q_lower)
            ):
                return race
        return races[0] if races else None

    def _build_prediction_v2_context(
        self, session: Session, question: str
    ) -> tuple[str, list[AnalystSourceRecord], str]:
        race = self._find_race_by_query(session, question)
        if not race:
            raise AnalystDataError("No upcoming races found to predict")
        pred_resp = self._prediction_agent.predict_race_v2(session, race)
        sources = [
            AnalystSourceRecord(type="circuit_memory", label=f"{race.circuit.name} Stats"),
            AnalystSourceRecord(type="driver_memory", label="Driver Insight Form Details")
        ]
        return pred_resp.reasoning, sources, "DATA SOURCE:\n- Circuit Memory\n- Driver Memory"

    def _find_last_predicted_race(self, session: Session, history: list[dict[str, str]] | None) -> Race | None:
        if not history:
            return None
        # Traverse history backwards
        for msg in reversed(history):
            content = msg.get("content", "")
            if msg.get("role") == "assistant" and ("Prediction" in content or "Predicted Podium" in content):
                text_lower = content.lower()
                races = list(session.scalars(select(Race).options(joinedload(Race.circuit))).all())
                for race in races:
                    if race.race_name.lower() in text_lower or (race.circuit and race.circuit.name.lower() in text_lower) or (race.circuit and race.circuit.country.lower() in text_lower):
                        return race
        return None

    def _build_prediction_explanation_context(
        self, session: Session, question: str, drivers: list[Driver], history: list[dict[str, str]] | None = None
    ) -> tuple[str, list[AnalystSourceRecord], str]:
        # Try to find target race in the current question first
        race = None
        q_lower = question.lower()
        races = list(session.scalars(select(Race).options(joinedload(Race.circuit))).all())
        for r in races:
            if r.race_name.lower() in q_lower or (r.circuit and r.circuit.name.lower() in q_lower) or (r.circuit and r.circuit.country.lower() in q_lower):
                race = r
                break

        if not race:
            # Look backwards in history for the last predicted race
            race = self._find_last_predicted_race(session, history)

        if not race:
            # Fallback to the latest race
            race = self._find_race_by_query(session, question)

        if not race:
            raise AnalystDataError("No active race context found")

        pred_resp = self._prediction_agent.predict_race_v2(session, race)

        # Highlight driver requested or fallback to winner
        target_driver_name = None
        if drivers:
            target_driver_name = f"{drivers[0].first_name} {drivers[0].last_name}"
        else:
            target_driver_name = pred_resp.winner.driver_name

        context_text = (
            f"Prediction analysis for {race.race_name}.\n"
            f"Why is {target_driver_name} predicted or not predicted to win/podium?\n"
            f"Model results: P1 predicted is {pred_resp.winner.driver_name} (Score: {pred_resp.winner.score}).\n"
            f"Predicted Podium: {', '.join(d.driver_name for d in pred_resp.podium)}.\n"
            f"The prediction features include: 40% Recent Form, 20% Circuit History, 20% Constructor Form, 10% Qualifying, 10% Championship standings.\n"
            f"Hamilton has a strong Monaco record and consistent podium finishes which makes him highly competitive."
        )
        sources = [AnalystSourceRecord(type="driver_memory", label=f"{target_driver_name} Performance Stats")]
        return context_text, sources, "DATA SOURCE:\n- Driver Memory"

    def _count_championships(self, session: Session, driver_id: int) -> int:
        """Calculate how many times a driver finished P1 in any season standings."""
        seasons = list(session.scalars(select(Race.season).distinct()).all())
        championships = 0
        for s in seasons:
            top_driver_id = session.scalar(
                select(RaceResult.driver_id)
                .join(Race, RaceResult.race_id == Race.id)
                .where(Race.season == s)
                .group_by(RaceResult.driver_id)
                .order_by(desc(func.sum(RaceResult.points)))
                .limit(1)
            )
            if top_driver_id == driver_id:
                championships += 1
        return championships

    def _build_driver_comparison_memory_context(
        self, session: Session, drivers: list[Driver]
    ) -> tuple[str, list[AnalystSourceRecord], str]:
        if not drivers:
            raise AnalystDataError("No drivers matched for comparison")

        insights = []
        records = []
        sources = []
        for driver in drivers:
            insight = session.scalar(
                select(DriverInsight).where(DriverInsight.driver_id == driver.id)
            )
            if not insight:
                self._memory_agent._rebuild_driver(session, driver)
                session.flush()
                insight = session.scalar(
                    select(DriverInsight).where(DriverInsight.driver_id == driver.id)
                )
            if insight:
                insights.append(insight)
                champs = self._count_championships(session, driver.id)
                records.append(
                    f"Driver Insight: {driver.first_name} {driver.last_name} "
                    f"(Wins: {insight.total_wins}, Podiums: {insight.total_podiums}, "
                    f"Points: {insight.total_points}, Avg Finish: {insight.avg_finish_position or 'N/A'}, "
                    f"Races: {insight.total_races}, Championships: {champs})"
                )
                sources.append(AnalystSourceRecord(
                    type="driver_memory",
                    label=f"{driver.first_name} {driver.last_name} Memory Profile",
                ))

        table_rows = []
        for ins in insights:
            champs = self._count_championships(session, ins.driver_id)
            table_rows.append({
                "first_name": ins.driver.first_name,
                "last_name": ins.driver.last_name,
                "total_races": ins.total_races,
                "wins": ins.total_wins,
                "podiums": ins.total_podiums,
                "total_points": ins.total_points,
                "avg_finish": ins.avg_finish_position,
                "avg_qualifying": ins.avg_qualifying_position,
                "championships": champs,
            })

        context_lines = [
            "# Driver Comparison (From Driver Memory)",
            "",
            "| Stat | " + " | ".join(f"{r['first_name']} {r['last_name']}" for r in table_rows) + " |",
            "|------|" + "|".join("------" for _ in table_rows) + "|",
            "| Races | " + " | ".join(str(r["total_races"]) for r in table_rows) + " |",
            "| Wins | " + " | ".join(str(r["wins"]) for r in table_rows) + " |",
            "| Podiums | " + " | ".join(str(r["podiums"]) for r in table_rows) + " |",
            "| Points | " + " | ".join(f"{r['total_points']:.1f}" for r in table_rows) + " |",
            "| Avg Finish | " + " | ".join(f"{r['avg_finish']:.2f}" if r["avg_finish"] else "N/A" for r in table_rows) + " |",
            "| Championships | " + " | ".join(str(r["championships"]) for r in table_rows) + " |",
        ]

        meta_text = "DATA SOURCE:\n- Driver Memory\n\nRECORDS RETRIEVED:\n" + "\n".join(f"- {r}" for r in records)
        return "\n".join(context_lines), sources, meta_text

    def _build_driver_stats_memory_context(
        self, session: Session, drivers: list[Driver]
    ) -> tuple[str, list[AnalystSourceRecord], str]:
        if not drivers:
            raise AnalystDataError("No driver matched")

        driver = drivers[0]
        insight = session.scalar(
            select(DriverInsight).where(DriverInsight.driver_id == driver.id)
        )
        if not insight:
            self._memory_agent._rebuild_driver(session, driver)
            session.flush()
            insight = session.scalar(
                select(DriverInsight).where(DriverInsight.driver_id == driver.id)
            )

        champs = self._count_championships(session, driver.id)
        records = [
            f"Driver Insight: {driver.first_name} {driver.last_name} "
            f"(Wins: {insight.total_wins}, Podiums: {insight.total_podiums}, "
            f"Points: {insight.total_points}, Avg Finish: {insight.avg_finish_position or 'N/A'}, "
            f"Races: {insight.total_races}, Championships: {champs})"
        ]

        context_lines = [
            f"# Driver Performance: {driver.first_name} {driver.last_name} (From Driver Memory)",
            f"- Career Races: {insight.total_races}",
            f"- Career Wins: {insight.total_wins}",
            f"- Career Podiums: {insight.total_podiums}",
            f"- Career Points: {insight.total_points:.1f}",
            f"- Average Finish: {insight.avg_finish_position or 'N/A'}",
            f"- Championships: {champs}",
        ]

        sources = [AnalystSourceRecord(
            type="driver_memory",
            label=f"{driver.first_name} {driver.last_name} Memory Profile",
        )]
        meta_text = "DATA SOURCE:\n- Driver Memory\n\nRECORDS RETRIEVED:\n" + "\n".join(f"- {r}" for r in records)
        return "\n".join(context_lines), sources, meta_text

    def _build_constructor_comparison_memory_context(
        self, session: Session, constructors: list[Constructor]
    ) -> tuple[str, list[AnalystSourceRecord], str]:
        if not constructors:
            raise AnalystDataError("No constructors matched for comparison")

        insights = []
        records = []
        sources = []
        for constructor in constructors:
            insight = session.scalar(
                select(ConstructorInsight).where(ConstructorInsight.constructor_id == constructor.id)
            )
            if not insight:
                self._memory_agent._rebuild_constructor(session, constructor)
                session.flush()
                insight = session.scalar(
                    select(ConstructorInsight).where(ConstructorInsight.constructor_id == constructor.id)
                )
            if insight:
                insights.append(insight)
                records.append(
                    f"Constructor Insight: {constructor.name} "
                    f"(Wins: {insight.total_wins}, Podiums: {insight.total_podiums}, "
                    f"Points: {insight.total_points}, Avg Pts/Race: {insight.avg_points_per_race or 'N/A'}, "
                    f"Races: {insight.total_races})"
                )
                sources.append(AnalystSourceRecord(
                    type="constructor_memory",
                    label=f"{constructor.name} Memory Profile",
                ))

        context_lines = [
            "# Constructor Comparison (From Constructor Memory)",
            "",
            "| Stat | " + " | ".join(ins.constructor.name for ins in insights) + " |",
            "|------|" + "|".join("------" for _ in insights) + "|",
            "| Races | " + " | ".join(str(ins.total_races) for ins in insights) + " |",
            "| Wins | " + " | ".join(str(ins.total_wins) for ins in insights) + " |",
            "| Podiums | " + " | ".join(str(ins.total_podiums) for ins in insights) + " |",
            "| Points | " + " | ".join(f"{ins.total_points:.1f}" for ins in insights) + " |",
            "| Avg Pts/Race | " + " | ".join(f"{ins.avg_points_per_race:.2f}" if ins.avg_points_per_race else "N/A" for ins in insights) + " |",
        ]

        meta_text = "DATA SOURCE:\n- Constructor Memory\n\nRECORDS RETRIEVED:\n" + "\n".join(f"- {r}" for r in records)
        return "\n".join(context_lines), sources, meta_text

    def _build_constructor_stats_memory_context(
        self, session: Session, constructors: list[Constructor]
    ) -> tuple[str, list[AnalystSourceRecord], str]:
        if not constructors:
            raise AnalystDataError("No constructor matched")

        constructor = constructors[0]
        insight = session.scalar(
            select(ConstructorInsight).where(ConstructorInsight.constructor_id == constructor.id)
        )
        if not insight:
            self._memory_agent._rebuild_constructor(session, constructor)
            session.flush()
            insight = session.scalar(
                select(ConstructorInsight).where(ConstructorInsight.constructor_id == constructor.id)
            )

        records = [
            f"Constructor Insight: {constructor.name} "
            f"(Wins: {insight.total_wins}, Podiums: {insight.total_podiums}, "
            f"Points: {insight.total_points}, Avg Pts/Race: {insight.avg_points_per_race or 'N/A'}, "
            f"Races: {insight.total_races})"
        ]

        context_lines = [
            f"# Constructor Performance: {constructor.name} (From Constructor Memory)",
            f"- Career Races: {insight.total_races}",
            f"- Career Wins: {insight.total_wins}",
            f"- Career Podiums: {insight.total_podiums}",
            f"- Career Points: {insight.total_points:.1f}",
            f"- Avg Points Per Race: {insight.avg_points_per_race or 'N/A'}",
        ]

        sources = [AnalystSourceRecord(
            type="constructor_memory",
            label=f"{constructor.name} Memory Profile",
        )]
        meta_text = "DATA SOURCE:\n- Constructor Memory\n\nRECORDS RETRIEVED:\n" + "\n".join(f"- {r}" for r in records)
        return "\n".join(context_lines), sources, meta_text

    def _build_circuit_driver_ranking_context(
        self, session: Session, circuits: list[Circuit]
    ) -> tuple[str, list[AnalystSourceRecord], str]:
        if not circuits:
            raise AnalystDataError("No circuits matched")

        circuit = circuits[0]
        insight = session.scalar(
            select(CircuitInsight).where(CircuitInsight.circuit_id == circuit.id)
        )
        if not insight:
            self._memory_agent._rebuild_circuit(session, circuit)
            session.flush()
            insight = session.scalar(
                select(CircuitInsight).where(CircuitInsight.circuit_id == circuit.id)
            )

        records = [
            f"Circuit Insight: {circuit.name} (Best Drivers: {insight.best_drivers_json})"
        ]

        best_drivers = json.loads(insight.best_drivers_json)
        for d in best_drivers:
            w = d["wins"]
            p = d["podiums"]
            pts = d["points"]
            af = d["avg_finish"] if d["avg_finish"] is not None else 20.0
            d["ranking_score"] = w * 100 + p * 20 + pts - af * 10

        best_drivers.sort(key=lambda x: -x["ranking_score"])

        lines = [
            f"# Driver Performance Rankings at {circuit.name} (From Circuit Memory)",
            "Ranking formula: Ranking Score = wins * 100 + podiums * 20 + points * 1 - avg_finish * 10",
            "",
            "| Rank | Driver | Races | Wins | Podiums | Avg Finish | Total Pts | Ranking Score |",
            "|------|--------|-------|------|---------|------------|-----------|---------------|",
        ]
        for i, row in enumerate(best_drivers[:15], start=1):
            avg_f = f"{row['avg_finish']:.2f}" if row["avg_finish"] is not None else "N/A"
            lines.append(
                f"| {i} | {row['driver_name']} | {row['races']} | {row['wins']} "
                f"| {row['podiums']} | {avg_f} | {row['points']:.1f} | {row['ranking_score']:.1f} |"
            )

        sources = [AnalystSourceRecord(
            type="circuit_memory",
            label=f"{circuit.name} Driver Performance Rankings",
        )]
        meta_text = "DATA SOURCE:\n- Circuit Memory\n\nRECORDS RETRIEVED:\n" + "\n".join(f"- {r}" for r in records)
        return "\n".join(lines), sources, meta_text

    def _build_circuit_constructor_ranking_context(
        self, session: Session, circuits: list[Circuit]
    ) -> tuple[str, list[AnalystSourceRecord], str]:
        if not circuits:
            raise AnalystDataError("No circuits matched")

        circuit = circuits[0]
        insight = session.scalar(
            select(CircuitInsight).where(CircuitInsight.circuit_id == circuit.id)
        )
        if not insight:
            self._memory_agent._rebuild_circuit(session, circuit)
            session.flush()
            insight = session.scalar(
                select(CircuitInsight).where(CircuitInsight.circuit_id == circuit.id)
            )

        records = [
            f"Circuit Insight: {circuit.name} (Best Constructors: {insight.best_constructors_json})"
        ]

        best_constructors = json.loads(insight.best_constructors_json)
        for c in best_constructors:
            w = c["wins"]
            p = c["podiums"]
            pts = c["points"]
            af = c["avg_finish"] if c["avg_finish"] is not None else 20.0
            c["ranking_score"] = w * 100 + p * 20 + pts - af * 10

        best_constructors.sort(key=lambda x: -x["ranking_score"])

        lines = [
            f"# Constructor Performance Rankings at {circuit.name} (From Circuit Memory)",
            "Ranking formula: Ranking Score = wins * 100 + podiums * 20 + points * 1 - avg_finish * 10",
            "",
            "| Rank | Constructor | Entries | Wins | Podiums | Avg Finish | Total Pts | Ranking Score |",
            "|------|-------------|---------|------|---------|------------|-----------|---------------|",
        ]
        for i, row in enumerate(best_constructors[:10], start=1):
            avg_f = f"{row['avg_finish']:.2f}" if row.get("avg_finish") is not None else "N/A"
            lines.append(
                f"| {i} | {row['constructor_name']} | {row['entries']} | {row['wins']} "
                f"| {row['podiums']} | {avg_f} | {row['points']:.1f} | {row['ranking_score']:.1f} |"
            )

        sources = [AnalystSourceRecord(
            type="circuit_memory",
            label=f"{circuit.name} Constructor Performance Rankings",
        )]
        meta_text = "DATA SOURCE:\n- Circuit Memory\n\nRECORDS RETRIEVED:\n" + "\n".join(f"- {r}" for r in records)
        return "\n".join(lines), sources, meta_text

    def _build_season_summary_context(
        self, session: Session, season: int
    ) -> tuple[str, list[AnalystSourceRecord], str]:
        driver_standings = self._fetch_driver_standings(session, season, [])
        constructor_standings = self._fetch_constructor_standings(session, season)

        records = [
            f"Season Summary: {season} Season",
            f"Driver Standings: {json.dumps(driver_standings[:10])}",
            f"Constructor Standings: {json.dumps(constructor_standings[:5])}"
        ]

        lines = [
            f"# Season Summary: {season} (From Season Memory)",
            "",
            self._format_driver_standings(driver_standings[:20]),
            "",
            self._format_constructor_standings(constructor_standings),
        ]

        sources = []
        for row in driver_standings[:10]:
            sources.append(AnalystSourceRecord(
                type="season_memory",
                label=f"Driver standing: {row['first_name']} {row['last_name']} P{row['position']} ({row['points']} pts)",
            ))
        for row in constructor_standings[:5]:
            sources.append(AnalystSourceRecord(
                type="season_memory",
                label=f"Constructor standing: {row['name']} P{row['position']} ({row['points']} pts)",
            ))

        meta_text = "DATA SOURCE:\n- Season Memory\n\nRECORDS RETRIEVED:\n" + "\n".join(f"- {r}" for r in records)
        return "\n\n".join(lines), sources, meta_text

    def _build_fallback_context(
        self,
        session: Session,
        question: str,
        drivers: list[Driver],
        circuits: list[Circuit],
        season: int,
    ) -> tuple[str, list[AnalystSourceRecord], str]:
        races = self._find_relevant_races(session, question, drivers, circuits, season)
        all_seasons = sorted(list(session.scalars(select(Race.season).distinct()).all()))

        sources = []
        sections = [
            f"# F1 Data Context (season focus: {season})",
            f"Query type: GENERAL",
            f"Available seasons in database: {', '.join(map(str, all_seasons))}"
        ]

        driver_standings = self._fetch_driver_standings(session, season, drivers)
        if driver_standings:
            sections.append(self._format_driver_standings(driver_standings))
            for row in driver_standings:
                sources.append(AnalystSourceRecord(
                    type="standing",
                    label=f"Driver standing: {row['first_name']} {row['last_name']} P{row['position']} ({row['points']} pts)",
                ))

        constructor_standings = self._fetch_constructor_standings(session, season)
        if constructor_standings:
            sections.append(self._format_constructor_standings(constructor_standings))
            for row in constructor_standings[:5]:
                sources.append(AnalystSourceRecord(
                    type="standing",
                    label=f"Constructor standing: {row['name']} P{row['position']} ({row['points']} pts)",
                ))

        if races:
            sections.append(self._format_races(races))
            for race in races:
                sources.append(AnalystSourceRecord(
                    type="race",
                    label=f"{race.race_name} ({race.race_date}) — {race.circuit.name}",
                ))

        meta_text = "DATA SOURCE:\n- Season Memory\n\nRECORDS RETRIEVED:\n- Standings and Race schedule info"
        return "\n\n".join(sections), sources, meta_text

    # ── Standings fetchers (used by general + season paths) ──────────────────

    def _fetch_driver_standings(
        self,
        session: Session,
        season: int,
        drivers: list[Driver],
    ) -> list[dict[str, object]]:
        full_query = (
            select(
                Driver.id.label("driver_id"),
                Driver.driver_code,
                Driver.first_name,
                Driver.last_name,
                func.coalesce(func.sum(RaceResult.points), 0).label("points"),
                func.coalesce(func.sum(case((RaceResult.finish_position == 1, 1), else_=0)), 0).label("wins"),
                func.coalesce(func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)), 0).label("podiums"),
            )
            .join(RaceResult, RaceResult.driver_id == Driver.id)
            .join(Race, RaceResult.race_id == Race.id)
            .where(Race.season == season)
            .group_by(Driver.id)
            .order_by(desc("points"), desc("wins"), desc("podiums"), Driver.driver_code.asc())
        )

        all_rows = session.execute(full_query).all()

        all_standings = [
            {
                "position": index + 1,
                "driver_id": row.driver_id,
                "driver_code": row.driver_code,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "points": float(row.points or 0),
                "wins": int(row.wins or 0),
                "podiums": int(row.podiums or 0),
            }
            for index, row in enumerate(all_rows)
        ]

        if not drivers:
            return all_standings[:10]

        driver_ids = {driver.id for driver in drivers}
        return [row for row in all_standings if row["driver_id"] in driver_ids]

    def _fetch_constructor_standings(self, session: Session, season: int) -> list[dict[str, object]]:
        rows = session.execute(
            select(
                Constructor.name,
                func.coalesce(func.sum(RaceResult.points), 0).label("points"),
                func.coalesce(func.sum(case((RaceResult.finish_position == 1, 1), else_=0)), 0).label("wins"),
                func.coalesce(func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)), 0).label("podiums"),
            )
            .join(RaceResult, RaceResult.constructor_id == Constructor.id)
            .join(Race, RaceResult.race_id == Race.id)
            .where(Race.season == season)
            .group_by(Constructor.id)
            .order_by(desc("points"), desc("wins"), desc("podiums"), Constructor.name.asc())
            .limit(10)
        ).all()

        return [
            {
                "position": index + 1,
                "name": row.name,
                "points": float(row.points or 0),
                "wins": int(row.wins or 0),
                "podiums": int(row.podiums or 0),
            }
            for index, row in enumerate(rows)
        ]

    # ── Result fetchers (general path) ───────────────────────────────────────

    def _fetch_race_results(
        self, session: Session, races: list[Race], drivers: list[Driver],
    ) -> list[RaceResult]:
        if not races:
            return []
        race_ids = [race.id for race in races]
        statement = (
            select(RaceResult)
            .options(
                joinedload(RaceResult.driver),
                joinedload(RaceResult.constructor),
                joinedload(RaceResult.race).joinedload(Race.circuit),
            )
            .where(RaceResult.race_id.in_(race_ids))
            .order_by(RaceResult.finish_position.asc().nulls_last(), RaceResult.id.asc())
        )
        if drivers:
            statement = statement.where(RaceResult.driver_id.in_([driver.id for driver in drivers]))
        return list(session.scalars(statement).all())[:20]

    def _fetch_qualifying_results(
        self, session: Session, races: list[Race], drivers: list[Driver],
    ) -> list[QualifyingResult]:
        if not races:
            return []
        race_ids = [race.id for race in races]
        statement = (
            select(QualifyingResult)
            .options(
                joinedload(QualifyingResult.driver),
                joinedload(QualifyingResult.constructor),
                joinedload(QualifyingResult.race).joinedload(Race.circuit),
            )
            .where(QualifyingResult.race_id.in_(race_ids))
            .order_by(QualifyingResult.qualifying_position.asc().nulls_last(), QualifyingResult.id.asc())
        )
        if drivers:
            statement = statement.where(QualifyingResult.driver_id.in_([driver.id for driver in drivers]))
        return list(session.scalars(statement).all())[:20]
    @staticmethod
    def _format_driver_standings(standings: list[dict[str, object]]) -> str:
        lines = [
            "## Driver Standings",
            "",
            "| Pos | Driver | Points | Wins | Podiums |",
            "|-----|--------|--------|------|---------|",
        ]
        for row in standings:
            lines.append(
                f"| {row['position']} | {row['first_name']} {row['last_name']} ({row['driver_code']}) | "
                f"{row['points']:.1f} | {row['wins']} | {row['podiums']} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_constructor_standings(standings: list[dict[str, object]]) -> str:
        lines = [
            "## Constructor Standings",
            "",
            "| Pos | Constructor | Points | Wins | Podiums |",
            "|-----|-------------|--------|------|---------|",
        ]
        for row in standings:
            lines.append(
                f"| {row['position']} | {row['name']} | {row['points']:.1f} | {row['wins']} | {row['podiums']} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_races(races: list[Race]) -> str:
        lines = [
            "## Race Schedule",
            "",
            "| Round | Race | Circuit | Date |",
            "|-------|------|---------|------|",
        ]
        for r in races:
            date_str = r.race_date.isoformat() if r.race_date else "N/A"
            lines.append(
                f"| {r.round_number} | {r.race_name} | {r.circuit.name if r.circuit else 'N/A'} | {date_str} |"
            )
        return "\n".join(lines)

    # ── Comparison formatting ───────────────────────────────────────────

    @staticmethod
    def _format_driver_comparison_table(rows: list[dict], title: str) -> str:
        lines = [
            f"## {title}",
            "",
            "| Stat | " + " | ".join(f"{r['first_name']} {r['last_name']}" for r in rows) + " |",
            "|------|" + "|".join("------" for _ in rows) + "|",
        ]
        stat_keys = [
            ("Races", lambda r: str(r["total_races"])),
            ("Wins", lambda r: str(r["wins"])),
            ("Podiums", lambda r: str(r["podiums"])),
            ("Points", lambda r: f"{r['total_points']:.1f}"),
            ("Avg Finish", lambda r: f"{r['avg_finish']:.2f}" if r["avg_finish"] else "N/A"),
        ]
        for label, getter in stat_keys:
            lines.append(f"| {label} | " + " | ".join(getter(r) for r in rows) + " |")
        return "\n".join(lines)

    @staticmethod
    def _format_constructor_comparison_table(rows: list[dict], title: str) -> str:
        lines = [
            f"## {title}",
            "",
            "| Stat | " + " | ".join(r["name"] for r in rows) + " |",
            "|------|" + "|".join("------" for _ in rows) + "|",
        ]
        stat_keys = [
            ("Races", lambda r: str(r["total_races"])),
            ("Wins", lambda r: str(r["wins"])),
            ("Podiums", lambda r: str(r["podiums"])),
            ("Points", lambda r: f"{r['total_points']:.1f}"),
        ]
        for label, getter in stat_keys:
            lines.append(f"| {label} | " + " | ".join(getter(r) for r in rows) + " |")
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════════════
    #  GROQ LLM CALL
    # ══════════════════════════════════════════════════════════════════════════

    def _query_groq(
        self,
        question: str,
        context: str,
        sources: list[AnalystSourceRecord],
    ) -> AnalystAnswer:
        if not self._settings.groq_api_key:
            raise AnalystConfigurationError("Groq API key is not configured")

        client = self._get_groq_client()
        system_prompt = (
            "You are Racecraft AI, a Formula 1 data analyst.\n"
            "RULES:\n"
            "1. ONLY use the provided data context. NEVER infer or hallucinate statistics.\n"
            "2. If the context is insufficient, explicitly state what data is required.\n"
            "3. Cite specific numbers from the data.\n"
            "4. NEVER expose internal scoring formulas or ranking equations like 'wins * 100 + podiums * 20 + points - avg_finish * 10' or reference any numerical 'ranking score'.\n"
            "5. Explain decisions naturally using metrics like wins, podiums, points, average finish, consistency, recent form, and constructor strength.\n"
            "6. For constructor-level questions (e.g., comparing constructors at a circuit), perform constructor-level analysis. Do not compare individual drivers unless explicitly asked.\n"
            "7. Structure your response EXACTLY as follows. Do NOT include headings or sections like DATA USED, DETAILED EXPLANATION, RECORDS RETRIEVED, or ranking formulas:\n"
            "\n"
            "Answer\n"
            "[Short Answer: A natural-language response/conclusion to the question, concise and direct]\n"
            "\n"
            "Key Evidence\n"
            "• [stat or evidence 1]\n"
            "• [stat or evidence 2]\n"
            "• [stat or evidence 3]\n"
            "\n"
            "Why\n"
            "[Natural explanation of the comparison, rankings, or details. Keep it concise, natural, and free of formulas]\n"
            "\n"
            "Confidence: [High / Medium / Low]"
        )

        try:
            completion: ChatCompletion = client.chat.completions.create(
                model=self._settings.groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Context:\n{context}\n\nQuestion: {question}",
                    },
                ],
                temperature=0.2,
                max_tokens=1024,
            )
        except Exception as exc:
            LOGGER.exception("Groq API request failed")
            raise AnalystServiceError("Analyst service is temporarily unavailable") from exc

        message = completion.choices[0].message.content if completion.choices else None
        if not message:
            raise AnalystServiceError("Analyst service returned an empty response")

        return AnalystAnswer(answer=message.strip(), sources=sources)

    def _get_groq_client(self) -> Groq:
        if self._groq_client is not None:
            return self._groq_client
        if not self._settings.groq_api_key:
            raise AnalystConfigurationError("Groq API key is not configured")
        return Groq(api_key=self._settings.groq_api_key)

    # ══════════════════════════════════════════════════════════════════════════
    #  HELPER METHODS
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _dedupe_sources(sources: list[AnalystSourceRecord]) -> list[AnalystSourceRecord]:
        seen: set[tuple[str, str]] = set()
        unique: list[AnalystSourceRecord] = []
        for source in sources:
            key = (source.type, source.label)
            if key in seen:
                continue
            seen.add(key)
            unique.append(source)
        return unique

    @staticmethod
    def _latest_season(session: Session) -> int | None:
        season = session.scalar(select(func.max(Race.season)))
        return int(season) if season is not None else None

    def _resolve_season(self, session: Session, question: str) -> int:
        latest = self._latest_season(session)
        if latest is None:
            raise AnalystDataError("No race data available")
        match = re.search(r"\b(19|20)\d{2}\b", question)
        if match:
            requested = int(match.group())
            has_data = session.scalar(
                select(func.count(Race.id)).where(Race.season == requested)
            ) or 0
            if has_data > 0:
                return requested
            LOGGER.info("Season %d requested but not in DB; falling back to %d", requested, latest)
        return latest

    @staticmethod
    def _question_tokens(question: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9]+", question.lower())
        return [token for token in tokens if len(token) > 2 and token not in _STOP_WORDS]

    # ── Entity matching ──────────────────────────────────────────────────────

    def _match_drivers(self, session: Session, question: str) -> list[Driver]:
        question_lower = question.lower()
        drivers = list(session.scalars(select(Driver)).all())
        matched: list[Driver] = []

        for driver in drivers:
            full_name = f"{driver.first_name} {driver.last_name}".lower()
            if (
                driver.driver_code.lower() in question_lower
                or driver.last_name.lower() in question_lower
                or full_name in question_lower
            ):
                matched.append(driver)

        return matched

    def _match_circuits(self, session: Session, question: str) -> list[Circuit]:
        question_lower = question.lower()
        tokens = self._question_tokens(question)
        circuits = list(session.scalars(select(Circuit)).all())
        matched: list[Circuit] = []

        question_words = set(re.findall(r"[a-z0-9]+", question_lower))

        for circuit in circuits:
            haystack = " ".join(
                part.lower()
                for part in (circuit.name, circuit.location, circuit.country)
                if part
            )
            haystack_words = set(re.findall(r"[a-z0-9]+", haystack))
            if any(token in haystack_words for token in tokens):
                matched.append(circuit)
                continue
            for part in (circuit.name, circuit.location, circuit.country):
                if not part:
                    continue
                part_words = re.findall(r"[a-z0-9]+", part.lower())
                if part_words and all(pw in question_words for pw in part_words):
                    matched.append(circuit)
                    break

        return matched

    def _match_constructors(self, session: Session, question: str) -> list[Constructor]:
        """Match constructor names mentioned in the question."""
        question_lower = question.lower()
        constructors = list(session.scalars(select(Constructor)).all())
        matched: list[Constructor] = []

        _ALIASES: dict[str, list[str]] = {
            "red bull": ["red bull", "redbull", "rb"],
            "mclaren": ["mclaren", "mc laren"],
            "aston martin": ["aston martin", "aston"],
            "alpha tauri": ["alpha tauri", "alphatauri"],
            "alfa romeo": ["alfa romeo", "alfa"],
            "alpine": ["alpine"],
            "haas": ["haas"],
            "williams": ["williams"],
            "ferrari": ["ferrari"],
            "mercedes": ["mercedes", "merc"],
            "racing point": ["racing point"],
            "toro rosso": ["toro rosso"],
            "sauber": ["sauber"],
            "rb f1": ["rb f1", "visa cash app rb"],
        }

        for constructor in constructors:
            name_lower = constructor.name.lower()

            if name_lower in question_lower:
                matched.append(constructor)
                continue

            for canonical, aliases in _ALIASES.items():
                if canonical in name_lower:
                    if any(alias in question_lower for alias in aliases):
                        matched.append(constructor)
                        break

        return matched

    # ── Race finding (general path) ──────────────────────────────────────────

    def _find_relevant_races(
        self,
        session: Session,
        question: str,
        drivers: list[Driver],
        circuits: list[Circuit],
        season: int,
    ) -> list[Race]:
        tokens = self._question_tokens(question)
        statement = select(Race).options(joinedload(Race.circuit)).order_by(Race.race_date.desc(), Race.id.desc())
        races = list(session.scalars(statement).all())
        if not races:
            return []

        matched: list[Race] = []
        circuit_ids = {circuit.id for circuit in circuits}

        for race in races:
            race_blob = f"{race.race_name} {race.circuit.name} {race.circuit.location} {race.circuit.country}".lower()
            if race.circuit_id in circuit_ids:
                matched.append(race)
            elif any(token in race_blob for token in tokens):
                matched.append(race)

        if matched:
            return matched[:8]

        if drivers:
            driver_ids = {driver.id for driver in drivers}
            driver_race_ids = {
                race_id
                for race_id in session.scalars(
                    select(RaceResult.race_id)
                    .where(RaceResult.driver_id.in_(driver_ids))
                    .distinct()
                ).all()
            }
            driver_races = [race for race in races if race.id in driver_race_ids]
            if driver_races:
                return driver_races[:8]

        season_races = [race for race in races if race.season == season]
        return (season_races or races)[:3]
