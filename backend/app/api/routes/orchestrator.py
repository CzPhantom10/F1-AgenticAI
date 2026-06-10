"""Orchestrator Agent API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.analyst_agent import AnalystConfigurationError, AnalystDataError, AnalystServiceError
from app.database.session import get_db
from app.schemas.analyst import AnalystQueryRequest, AnalystQueryResponse, AnalystSource

LOGGER = logging.getLogger(__name__)

orchestrator_router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])


@orchestrator_router.post("/query", response_model=AnalystQueryResponse)
def orchestrator_query(
    body: AnalystQueryRequest,
    db: Session = Depends(get_db),
) -> AnalystQueryResponse:
    """Answer a natural-language F1 question using orchestrated agents and Groq."""
    agent = OrchestratorAgent()

    try:
        history_list = [h.model_dump() for h in body.history] if body.history else None
        result = agent.answer(db, body.question, history=history_list)
    except AnalystConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AnalystDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        LOGGER.exception("Orchestrator query failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return AnalystQueryResponse(
        answer=result.answer,
        sources=[AnalystSource(type=source.type, label=source.label) for source in result.sources],
    )
