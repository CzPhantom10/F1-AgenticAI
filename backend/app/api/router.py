"""Top-level API router for Racecraft AI."""

from fastapi import APIRouter

from app.api.routes.admin import admin_router
from app.api.routes.analyst import analyst_router
from app.api.routes.orchestrator import orchestrator_router
from app.api.routes.resources import (
	constructors_router,
	drivers_router,
	standings_router,
	qualifying_router,
	races_router,
	results_router,
)
from app.api.routes.system import router as system_router, seasons_router
from app.api.routes.memory import router as memory_router
from app.api.routes.prediction import router as prediction_router


api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(seasons_router)
api_router.include_router(races_router)
api_router.include_router(drivers_router)
api_router.include_router(constructors_router)
api_router.include_router(standings_router)
api_router.include_router(results_router)
api_router.include_router(qualifying_router)
api_router.include_router(analyst_router)
api_router.include_router(orchestrator_router)
api_router.include_router(memory_router)
api_router.include_router(prediction_router)
api_router.include_router(admin_router)