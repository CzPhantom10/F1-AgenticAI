"""Admin endpoints for Racecraft AI operational tasks."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.sync import SyncResponse, RaceImportDetail
from app.services.data_sync import DataSyncService


LOGGER = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/admin", tags=["Admin"])


@admin_router.post(
    "/sync",
    response_model=SyncResponse,
    summary="Manually trigger a database synchronisation",
    description=(
        "Compares the latest completed race in the database with FastF1 and "
        "imports any missing races incrementally. "
        "Returns a summary of what was imported."
    ),
)
def manual_sync() -> SyncResponse:
    """Trigger an incremental database sync and return a structured summary."""
    LOGGER.info("[Admin] Manual sync triggered via POST /admin/sync")

    try:
        service = DataSyncService()
        result = service.sync_missing_races()
    except Exception as exc:
        LOGGER.error("[Admin] Sync endpoint raised unexpected error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {exc}",
        ) from exc

    # Convert internal dataclasses → Pydantic models
    race_details = [
        RaceImportDetail(
            season=r.season,
            round_number=r.round_number,
            race_name=r.race_name,
            race_results_imported=r.race_results_imported,
            qualifying_results_imported=r.qualifying_results_imported,
            success=r.success,
            error=r.error,
        )
        for r in result.races
    ]

    return SyncResponse(
        updated=result.updated,
        new_races=result.new_races,
        drivers_updated=result.drivers_updated,
        constructors_updated=result.constructors_updated,
        seasons_touched=result.seasons_touched,
        races=race_details,
        message=result.message,
    )
