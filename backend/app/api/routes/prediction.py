"""Prediction API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.agents.prediction_agent import PredictionAgent
from app.schemas.prediction import PredictionResponse

router = APIRouter(prefix="/predict", tags=["Prediction"])
agent = PredictionAgent()


@router.post("/race/{race_id}", response_model=PredictionResponse)
def predict_race(race_id: int, db: Session = Depends(get_db)) -> PredictionResponse:
    """Predict race results (winner, podium, top 10) for a given race ID."""
    try:
        return agent.predict_race(db, race_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during prediction: {exc}",
        )
