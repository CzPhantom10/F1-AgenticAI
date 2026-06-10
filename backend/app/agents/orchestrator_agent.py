"""Orchestrator Agent — coordinates Data Agent, Memory Agent, Prediction Agent, and Analyst Agent."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from groq import Groq
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.agents.analyst_agent import AnalystAgent, AnalystSourceRecord, AnalystAnswer, QueryType
from app.agents.prediction_agent import PredictionAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.data_agent import DataAgent

LOGGER = logging.getLogger(__name__)

class OrchestratorAgent:
    """Orchestrates F1 intelligence agents, aggregates context, and runs Groq reasoning."""

    def __init__(
        self,
        settings: Settings | None = None,
        groq_client: Groq | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._groq_client = groq_client
        self._analyst_agent = AnalystAgent(settings=self._settings, groq_client=self._groq_client)
        self._prediction_agent = PredictionAgent()
        self._memory_agent = MemoryAgent()
        self._data_agent = DataAgent()

    def answer(
        self,
        session: Session,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> AnalystAnswer:
        """Analyze, plan, execute tools, aggregate context, and reason via Groq."""
        start_time = time.perf_counter()
        normalized_question = question.strip()

        # 1. Resolve entities & inherit history context
        drivers = self._analyst_agent._match_drivers(session, normalized_question)
        circuits = self._analyst_agent._match_circuits(session, normalized_question)
        constructors = self._analyst_agent._match_constructors(session, normalized_question)

        # Inherit matched entities from history if not present in current query
        inherited_drivers = list(drivers)
        inherited_circuits = list(circuits)
        inherited_constructors = list(constructors)

        if history:
            for msg in reversed(history):
                content = msg.get("content", "")
                if msg.get("role") == "user":
                    if not inherited_drivers:
                        inherited_drivers = self._analyst_agent._match_drivers(session, content)
                    if not inherited_circuits:
                        inherited_circuits = self._analyst_agent._match_circuits(session, content)
                    if not inherited_constructors:
                        inherited_constructors = self._analyst_agent._match_constructors(session, content)

        # 2. Query Planning
        plan = self.plan_query(normalized_question, inherited_drivers, inherited_circuits, inherited_constructors)

        # 3. Execution & Context Aggregation
        aggregated_context: dict[str, Any] = {}
        sources: list[AnalystSourceRecord] = []

        # Find relevant race for predictions or circuit context
        target_race = None
        if inherited_circuits:
            # Match race for this circuit in current year or latest year
            target_race = self._analyst_agent._find_race_by_query(session, normalized_question)
            if not target_race:
                # Fallback to circuit match in history
                for c in inherited_circuits:
                    target_race = session.query(self._prediction_agent._model_race).filter_by(circuit_id=c.id).first()
                    if target_race:
                        break
        else:
            # Fallback to last predicted race or upcoming race
            target_race = self._analyst_agent._find_last_predicted_race(session, history)
            if not target_race:
                target_race = self._analyst_agent._find_race_by_query(session, normalized_question)

        if "PredictionAgent" in plan and target_race:
            try:
                pred_resp = self._prediction_agent.predict_race_v2(session, target_race)
                aggregated_context["prediction"] = {
                    "winner": pred_resp.winner.model_dump() if hasattr(pred_resp.winner, "model_dump") else pred_resp.winner.__dict__,
                    "podium": [p.model_dump() if hasattr(p, "model_dump") else p.__dict__ for p in pred_resp.podium],
                    "top_10": [p.model_dump() if hasattr(p, "model_dump") else p.__dict__ for p in pred_resp.top_10],
                    "confidence_score": pred_resp.confidence_score,
                    "evidence": pred_resp.evidence,
                    "reasoning": pred_resp.reasoning,
                }
                sources.append(AnalystSourceRecord(type="prediction", label=f"{target_race.race_name} Predictions"))
            except Exception as e:
                LOGGER.error("PredictionAgent execution failed: %s", e)

        if "CircuitMemory" in plan and inherited_circuits:
            circuit = inherited_circuits[0]
            try:
                if inherited_constructors:
                    c_ctx, c_src, _ = self._analyst_agent._build_circuit_constructor_ranking_context(session, inherited_circuits)
                else:
                    c_ctx, c_src, _ = self._analyst_agent._build_circuit_driver_ranking_context(session, inherited_circuits)
                aggregated_context["circuit_memory"] = c_ctx
                sources.extend(c_src)
            except Exception as e:
                LOGGER.error("CircuitMemory execution failed: %s", e)

        if "DriverMemory" in plan and inherited_drivers:
            try:
                if len(inherited_drivers) >= 2:
                    d_ctx, d_src, _ = self._analyst_agent._build_driver_comparison_memory_context(session, inherited_drivers)
                else:
                    d_ctx, d_src, _ = self._analyst_agent._build_driver_stats_memory_context(session, inherited_drivers)
                aggregated_context["driver_memory"] = d_ctx
                sources.extend(d_src)
            except Exception as e:
                LOGGER.error("DriverMemory execution failed: %s", e)

        if "ConstructorMemory" in plan and inherited_constructors:
            try:
                if len(inherited_constructors) >= 2:
                    t_ctx, t_src, _ = self._analyst_agent._build_constructor_comparison_memory_context(session, inherited_constructors)
                else:
                    t_ctx, t_src, _ = self._analyst_agent._build_constructor_stats_memory_context(session, inherited_constructors)
                aggregated_context["constructor_memory"] = t_ctx
                sources.extend(t_src)
            except Exception as e:
                LOGGER.error("ConstructorMemory execution failed: %s", e)

        if "HistoricalStats" in plan:
            try:
                season = self._analyst_agent._resolve_season(session, normalized_question)
                s_ctx, s_src, _ = self._analyst_agent._build_fallback_context(session, normalized_question, inherited_drivers, inherited_circuits, season)
                aggregated_context["historical_stats"] = s_ctx
                sources.extend(s_src)
            except Exception as e:
                LOGGER.error("HistoricalStats execution failed: %s", e)

        # Fallback if context is completely empty
        if not aggregated_context:
            season = self._analyst_agent._resolve_season(session, normalized_question)
            fallback_ctx, fallback_src, _ = self._analyst_agent._build_fallback_context(session, normalized_question, inherited_drivers, inherited_circuits, season)
            aggregated_context["fallback"] = fallback_ctx
            sources.extend(fallback_src)

        sources = self._analyst_agent._dedupe_sources(sources)
        context_str = json.dumps(aggregated_context, indent=2)

        # 4. Groq Reasoning / Answer Generation
        # For direct race prediction or next race schedule, return predicted reasoning directly to match exact formatting
        q_lower = normalized_question.lower()
        if "next race" in q_lower or "upcoming race" in q_lower:
            ans_text = self._prediction_agent.find_next_race(session)
            ans = AnalystAnswer(answer=ans_text, sources=sources)
        elif ("predict" in q_lower or "who will win" in q_lower or "who wins" in q_lower) and not ("why" in q_lower or "explain" in q_lower or "what about" in q_lower):
            # Direct prediction requests
            if target_race:
                pred_resp = self._prediction_agent.predict_race_v2(session, target_race)
                ans = AnalystAnswer(answer=pred_resp.reasoning, sources=sources)
            else:
                ans = self._query_groq(normalized_question, context_str, sources)
        else:
            ans = self._query_groq(normalized_question, context_str, sources)

        # 5. Debug Logging
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        LOGGER.info(
            "Query: %s\nPlan: %s\nSelected Agents: %d\nExecution Time: %dms",
            normalized_question,
            plan,
            len(plan),
            execution_time_ms,
        )

        return ans

    def plan_query(self, question: str, drivers: list[Any], circuits: list[Any], constructors: list[Any]) -> list[str]:
        """Classify question and plan required capabilities."""
        plan = []
        q_lower = question.lower()

        # Check for prediction intent
        is_prediction = any(w in q_lower for w in ["predict", "prediction", "will win", "who wins", "who would win", "podium", "beat"])

        if circuits:
            plan.append("CircuitMemory")
        if drivers:
            plan.append("DriverMemory")
        if constructors:
            plan.append("ConstructorMemory")
        if is_prediction:
            if "PredictionAgent" not in plan:
                plan.append("PredictionAgent")
            if "DriverMemory" not in plan:
                plan.append("DriverMemory")
            if "CircuitMemory" not in plan and circuits:
                plan.append("CircuitMemory")

        # Check for historical stats / comparisons / summaries
        is_historical = any(w in q_lower for w in ["career", "stats", "history", "standing", "standings", "results", "compare", "summary"])
        if is_historical and drivers and not is_prediction:
            plan.append("HistoricalStats")

        # Ensure distinct order
        return list(dict.fromkeys(plan))

    def _query_groq(
        self,
        question: str,
        context: str,
        sources: list[AnalystSourceRecord],
    ) -> AnalystAnswer:
        if not self._settings.groq_api_key:
            raise RuntimeError("Groq API key is not configured")

        client = Groq(api_key=self._settings.groq_api_key)
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

        completion = client.chat.completions.create(
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

        message = completion.choices[0].message.content if completion.choices else None
        if not message:
            raise RuntimeError("Groq API returned empty response")

        return AnalystAnswer(answer=message.strip(), sources=sources)
