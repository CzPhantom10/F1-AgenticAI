"""SQLite database configuration and shared SQLAlchemy session objects."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.database.base import Base


settings = get_settings()

engine_kwargs: dict[str, object] = {}
if settings.database_url.startswith("sqlite"):
	engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_kwargs)

SessionLocal = sessionmaker(
	autocommit=False,
	autoflush=False,
	bind=engine,
	expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
	"""Yield a database session and always close it afterwards."""

	db_session = SessionLocal()
	try:
		yield db_session
	finally:
		db_session.close()


def ping_database() -> bool:
	"""Run a lightweight query to verify the SQLite connection."""

	with engine.connect() as connection:
		connection.execute(text("SELECT 1"))

	return True


__all__ = ["Base", "SessionLocal", "engine", "get_db", "ping_database"]