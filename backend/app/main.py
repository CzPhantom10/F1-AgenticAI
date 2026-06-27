"""FastAPI application entrypoint for Racecraft AI."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings


LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan handler.

    Runs *before* the server accepts requests (startup phase) and
    *after* the last request is served (shutdown phase).
    """
    # ── Startup ───────────────────────────────────────────────────────────────
    # 1. Ensure all database tables exist.
    from app.database.init_db import init_db
    try:
        init_db()
        LOGGER.info("[Startup] Database tables initialised.")
    except Exception as exc:
        LOGGER.error("[Startup] Database initialisation failed: %s", exc)

    # 2. Incrementally sync any missing race data from FastF1.
    from app.services.data_sync import DataSyncService
    DataSyncService().run_startup_sync()

    yield  # ← server is live and handling requests here

    # ── Shutdown (nothing needed yet) ─────────────────────────────────────────
    LOGGER.info("[Shutdown] Application shutting down.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()