"""Pydantic schemas for F1 prediction results."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PredictionDetail(BaseModel):
    """Pydantic model representing prediction details for a single driver."""

    model_config = ConfigDict(from_attributes=True)

    driver_id: int
    driver_name: str
    driver_code: str
    predicted_position: int
    score: float


class PredictionResponse(BaseModel):
    """Structured response for F1 predictions."""

    winner: PredictionDetail
    podium: list[PredictionDetail]
    top_10: list[PredictionDetail]
    confidence_score: float
    evidence: list[str]
    reasoning: str
