"""Memory insights API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.agents.memory_agent import MemoryAgent
from app.schemas.memory import (
    MemoryRebuildResponse,
    DriverInsightRead,
    ConstructorInsightRead,
    CircuitInsightRead,
)

router = APIRouter(prefix="/memory", tags=["Memory"])
agent = MemoryAgent()


@router.post("/rebuild", response_model=MemoryRebuildResponse)
def rebuild_memory(db: Session = Depends(get_db)) -> MemoryRebuildResponse:
    """Trigger a full rebuild of driver, constructor, and circuit insights."""
    stats = agent.rebuild_all(db)
    return MemoryRebuildResponse(
        success=stats.success,
        drivers_processed=stats.drivers_processed,
        constructors_processed=stats.constructors_processed,
        circuits_processed=stats.circuits_processed,
        errors=stats.errors,
    )


@router.get("/driver/{driver_id}", response_model=DriverInsightRead)
def get_driver_insight(driver_id: int, db: Session = Depends(get_db)) -> DriverInsightRead:
    """Retrieve pre-computed insights for a specific driver."""
    insight = agent.get_driver_insight(db, driver_id)
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pre-computed insight found for driver ID {driver_id}",
        )
    return insight


@router.get("/constructor/{constructor_id}", response_model=ConstructorInsightRead)
def get_constructor_insight(constructor_id: int, db: Session = Depends(get_db)) -> ConstructorInsightRead:
    """Retrieve pre-computed insights for a specific constructor."""
    insight = agent.get_constructor_insight(db, constructor_id)
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pre-computed insight found for constructor ID {constructor_id}",
        )
    return insight


@router.get("/circuit/{circuit_id}", response_model=CircuitInsightRead)
def get_circuit_insight(circuit_id: int, db: Session = Depends(get_db)) -> CircuitInsightRead:
    """Retrieve pre-computed insights for a specific circuit."""
    insight = agent.get_circuit_insight(db, circuit_id)
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pre-computed insight found for circuit ID {circuit_id}",
        )
    return insight
