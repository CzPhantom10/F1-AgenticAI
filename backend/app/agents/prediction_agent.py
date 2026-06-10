"""Prediction Agent V2 — precise F1 scoring model, confidence calculator, next race scheduling, and intents routing."""

from __future__ import annotations

import json
import logging
import math
from datetime import date
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings, get_settings
from app.models import (
    Race,
    Driver,
    Constructor,
    RaceResult,
    QualifyingResult,
    DriverInsight,
    ConstructorInsight,
    CircuitInsight,
)
from app.agents.memory_agent import MemoryAgent
from app.schemas.prediction import PredictionDetail, PredictionResponse

LOGGER = logging.getLogger(__name__)


class PredictionAgent:
    """Evaluate driver and constructor historical data to predict race results."""

    def __init__(
        self,
        settings: Settings | None = None,
        groq_client: None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._memory_agent = MemoryAgent()

    def find_next_race(self, session: Session) -> str:
        """Find the nearest future race based on current date (2026-06-10)."""
        today = date(2026, 6, 10)
        statement = (
            select(Race)
            .options(joinedload(Race.circuit))
            .where(Race.race_date > today)
            .order_by(Race.race_date.asc())
        )
        next_race = session.scalar(statement)
        if not next_race:
            # Fall back to latest race in DB if none in future
            next_race = session.scalar(select(Race).options(joinedload(Race.circuit)).order_by(Race.race_date.desc()))

        if next_race:
            name = next_race.race_name.replace("Grand Prix", "GP").strip()
            formatted_date = f"{next_race.race_date.day} {next_race.race_date.strftime('%B %Y')}"
            return f"{name}\n{formatted_date}"
        return "No upcoming races found in the schedule."

    def predict_race_v2(self, session: Session, race: Race) -> PredictionResponse:
        """Calculate and generate F1 prediction results using V2 weighted scoring model."""
        drivers = list(session.scalars(select(Driver)).all())
        if not drivers:
            raise ValueError("No drivers found in the database to predict")

        # Get max driver standings points in current season before target race
        max_driver_points = session.scalar(
            select(func.sum(RaceResult.points))
            .join(Race, RaceResult.race_id == Race.id)
            .where(
                Race.season == race.season,
                Race.race_date < race.race_date
            )
            .group_by(RaceResult.driver_id)
            .order_by(desc(func.sum(RaceResult.points)))
            .limit(1)
        ) or 0

        # Get max constructor points in the current season before target race
        max_constructor_points = session.scalar(
            select(func.sum(RaceResult.points))
            .join(Race, RaceResult.race_id == Race.id)
            .where(
                Race.season == race.season,
                Race.race_date < race.race_date
            )
            .group_by(RaceResult.constructor_id)
            .order_by(desc(func.sum(RaceResult.points)))
            .limit(1)
        ) or 0

        driver_scores = []
        for driver in drivers:
            # Rebuild memories if needed
            driver_insight = session.scalar(
                select(DriverInsight).where(DriverInsight.driver_id == driver.id)
            )
            if not driver_insight:
                self._memory_agent._rebuild_driver(session, driver)
                session.flush()
                driver_insight = session.scalar(
                    select(DriverInsight).where(DriverInsight.driver_id == driver.id)
                )

            # Determine constructor
            result = session.scalar(
                select(RaceResult)
                .where(RaceResult.race_id == race.id, RaceResult.driver_id == driver.id)
            )
            constructor = None
            if result:
                constructor = session.scalar(
                    select(Constructor).where(Constructor.id == result.constructor_id)
                )
            else:
                last_result = session.scalars(
                    select(RaceResult)
                    .where(RaceResult.driver_id == driver.id)
                    .order_by(RaceResult.id.desc())
                ).first()
                if last_result:
                    constructor = session.scalar(
                        select(Constructor).where(Constructor.id == last_result.constructor_id)
                    )

            constructor_insight = None
            if constructor:
                constructor_insight = session.scalar(
                    select(ConstructorInsight).where(ConstructorInsight.constructor_id == constructor.id)
                )
                if not constructor_insight:
                    self._memory_agent._rebuild_constructor(session, constructor)
                    session.flush()
                    constructor_insight = session.scalar(
                        select(ConstructorInsight).where(ConstructorInsight.constructor_id == constructor.id)
                    )

            # ── 1. RECENT FORM (40%) ──
            # Query last 5 race results prior to the target race's date
            recent_results = session.execute(
                select(RaceResult.finish_position, RaceResult.points)
                .join(Race, RaceResult.race_id == Race.id)
                .where(
                    RaceResult.driver_id == driver.id,
                    Race.race_date < race.race_date
                )
                .order_by(Race.race_date.desc(), Race.round_number.desc())
                .limit(5)
            ).all()

            recent_form_score = 50.0
            if recent_results:
                wins = sum(1 for r in recent_results if r.finish_position == 1)
                podiums = sum(1 for r in recent_results if r.finish_position is not None and r.finish_position <= 3)
                points = sum(r.points for r in recent_results if r.points is not None)
                finishes = [r.finish_position for r in recent_results if r.finish_position is not None]
                avg_f = sum(finishes) / len(finishes) if finishes else 10.0

                win_score = (wins / 5.0) * 100
                podium_score = (podiums / 5.0) * 100
                points_score = (points / 130.0) * 100
                finish_score = ((20.0 - avg_f) / 19.0) * 100
                recent_form_score = 0.3 * win_score + 0.3 * podium_score + 0.2 * points_score + 0.2 * finish_score
            elif driver_insight:
                recent_form = json.loads(driver_insight.recent_form_json)
                if recent_form:
                    wins = sum(1 for r in recent_form if r["finish"] == 1)
                    podiums = sum(1 for r in recent_form if r["finish"] is not None and r["finish"] <= 3)
                    points = sum(r["points"] for r in recent_form if r["points"] is not None)
                    finishes = [r["finish"] for r in recent_form if r["finish"] is not None]
                    avg_f = sum(finishes) / len(finishes) if finishes else 10.0

                    win_score = (wins / 5.0) * 100
                    podium_score = (podiums / 5.0) * 100
                    points_score = (points / 130.0) * 100
                    finish_score = ((20.0 - avg_f) / 19.0) * 100
                    recent_form_score = 0.3 * win_score + 0.3 * podium_score + 0.2 * points_score + 0.2 * finish_score

            # ── 2. CIRCUIT HISTORY (20%) ──
            circuit_insight = session.scalar(
                select(CircuitInsight).where(CircuitInsight.circuit_id == race.circuit_id)
            )
            if not circuit_insight:
                self._memory_agent._rebuild_circuit(session, race.circuit)
                session.flush()
                circuit_insight = session.scalar(
                    select(CircuitInsight).where(CircuitInsight.circuit_id == race.circuit_id)
                )

            circuit_score = 40.0
            if circuit_insight:
                best_drivers = json.loads(circuit_insight.best_drivers_json)
                driver_record = next((d for d in best_drivers if d["driver_id"] == driver.id), None)
                if driver_record:
                    w = driver_record.get("wins", 0)
                    p = driver_record.get("podiums", 0)
                    af = driver_record.get("avg_finish")
                    apps = driver_record.get("races", 0)

                    win_rate = (w / apps * 100) if apps > 0 else 0
                    podium_rate = (p / apps * 100) if apps > 0 else 0
                    af_score = ((20.0 - af) / 19.0 * 100) if (af is not None and apps > 0) else 0
                    apps_score = min(100.0, apps * 20.0)

                    circuit_score = 0.4 * win_rate + 0.3 * podium_rate + 0.2 * af_score + 0.1 * apps_score

            # ── 3. CONSTRUCTOR FORM (20%) ──
            constructor_score = 50.0
            if constructor:
                constructor_season_points = session.scalar(
                    select(func.coalesce(func.sum(RaceResult.points), 0))
                    .join(Race, RaceResult.race_id == Race.id)
                    .where(
                        RaceResult.constructor_id == constructor.id,
                        Race.season == race.season,
                        Race.race_date < race.race_date
                    )
                ) or 0
                if max_constructor_points > 0:
                    constructor_score = (constructor_season_points / max_constructor_points) * 100
                elif constructor_insight and constructor_insight.avg_points_per_race is not None:
                    constructor_score = min(100.0, (constructor_insight.avg_points_per_race / 44.0) * 100)

            # ── 4. QUALIFYING PERFORMANCE (10%) ──
            qual_result = session.scalar(
                select(QualifyingResult)
                .where(QualifyingResult.race_id == race.id, QualifyingResult.driver_id == driver.id)
            )
            grid = 10.0
            if qual_result:
                grid = qual_result.qualifying_position
            elif driver_insight and driver_insight.avg_qualifying_position is not None:
                grid = driver_insight.avg_qualifying_position

            qualifying_score = max(0.0, 100.0 - (grid - 1) * 5.0)

            # ── 5. CHAMPIONSHIP STANDINGS (10%) ──
            standings_score = 50.0
            standings_points = session.scalar(
                select(func.coalesce(func.sum(RaceResult.points), 0))
                .join(Race, RaceResult.race_id == Race.id)
                .where(
                    RaceResult.driver_id == driver.id,
                    Race.season == race.season,
                    Race.race_date < race.race_date
                )
            ) or 0
            if max_driver_points > 0:
                standings_score = (standings_points / max_driver_points) * 100
            elif driver_insight and driver_insight.total_points is not None:
                standings_score = min(100.0, (driver_insight.total_points / 500.0) * 100)

            # ── COMPOSITE SCORE ──
            composite = (
                (0.4 * recent_form_score)
                + (0.2 * circuit_score)
                + (0.2 * constructor_score)
                + (0.1 * qualifying_score)
                + (0.1 * standings_score)
            )

            # Internal debugging log
            LOGGER.debug(
                "Driver %s: recent_form_score=%s, circuit_score=%s, constructor_score=%s, qualifying_score=%s, standings_score=%s, composite=%s",
                driver.driver_code,
                recent_form_score,
                circuit_score,
                constructor_score,
                qualifying_score,
                standings_score,
                composite,
            )

            driver_scores.append({
                "driver_id": driver.id,
                "driver_name": f"{driver.first_name} {driver.last_name}",
                "driver_code": driver.driver_code,
                "score": round(composite, 2),
                "features": [recent_form_score, circuit_score, constructor_score, qualifying_score, standings_score],
            })

        driver_scores.sort(key=lambda x: -x["score"])

        details = [
            PredictionDetail(
                driver_id=d["driver_id"],
                driver_name=d["driver_name"],
                driver_code=d["driver_code"],
                predicted_position=idx + 1,
                score=d["score"],
            )
            for idx, d in enumerate(driver_scores)
        ]

        winner = details[0]
        podium = details[:3]
        top_10 = details[:10]

        # Calculate Confidence Score dynamically
        top_features = driver_scores[0]["features"]
        completeness = sum(1 for f in top_features if f > 0) / 5.0
        
        # races available: recent races and circuit history
        recent_count = len(recent_results) if recent_results else 0
        
        winner_driver_id = winner.driver_id
        winner_record = None
        if circuit_insight:
            best_drivers = json.loads(circuit_insight.best_drivers_json)
            winner_record = next((d for d in best_drivers if d["driver_id"] == winner_driver_id), None)
        circuit_count = winner_record.get("races", 0) if winner_record else 0
        
        races_available = min(10, recent_count + circuit_count)
        races_factor = races_available / 10.0
        
        mean_val = sum(top_features) / len(top_features)
        var_val = sum((x - mean_val) ** 2 for x in top_features) / len(top_features)
        std_dev = math.sqrt(var_val)
        agreement = max(0.0, 1.0 - (std_dev / 50.0))
        
        confidence_val = round(50.0 + (completeness * 20.0) + (races_factor * 15.0) + (agreement * 10.0), 1)
        confidence_val = max(50.0, min(95.0, confidence_val))

        # Format output exactly as requested
        reasons = [
            "• Winner predicted based on strong recent form in recent races, showing consistent finishes.",
            f"• Excellent track record and familiarity with the {race.circuit.name} layout.",
            "• Highly competitive constructor form contributing to race pace."
        ]

        podium_lines = []
        for idx, p in enumerate(podium):
            podium_lines.append(f"{idx+1}. {p.driver_name}")
        podium_text = "\n".join(podium_lines)

        confidence_category = "High" if confidence_val >= 80.0 else ("Medium" if confidence_val >= 60.0 else "Low")

        reasoning_text = (
            f"🏁 {race.race_name} Prediction\n\n"
            "Predicted Podium\n\n"
            f"{podium_text}\n\n"
            f"Confidence: {confidence_category} ({confidence_val:.1f}%)\n\n"
            "Factors Considered\n"
            "• Circuit performance history\n"
            "• Recent form\n"
            "• Podiums at this circuit\n"
            "• Average finishing position\n"
            "• Constructor strength\n\n"
            "Reasons:\n"
            + "\n".join(reasons)
        )

        return PredictionResponse(
            winner=winner,
            podium=podium,
            top_10=top_10,
            confidence_score=confidence_val,
            evidence=reasons,
            reasoning=reasoning_text,
        )

    def predict_race(self, session: Session, race_id: int) -> PredictionResponse:
        """Calculates prediction for backward compatibility."""
        race = session.scalar(select(Race).where(Race.id == race_id))
        if not race:
            raise ValueError(f"Race with ID {race_id} does not exist")
        return self.predict_race_v2(session, race)
