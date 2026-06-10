"""Environment-driven application settings."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _build_database_url() -> str:
    """Build the SQLite URL from environment variables."""

    explicit_url = getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    database_path = Path(__file__).resolve().parents[2] / "racecraft_ai.db"
    return f"sqlite:///{database_path.as_posix()}"


def _parse_bool(value: str | None, default: bool = False) -> bool:
    """Parse a boolean-like environment variable value."""

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable application settings container."""

    app_name: str
    app_version: str
    environment: str
    debug: bool
    database_url: str
    cors_origins: tuple[str, ...]
    groq_api_key: str | None
    groq_model: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings so the app loads config once per process."""

    cors_origins = tuple(
        origin.strip()
        for origin in getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    )

    groq_api_key = getenv("GROQ_API_KEY")
    if groq_api_key is not None:
        groq_api_key = groq_api_key.strip() or None

    return Settings(
        app_name=getenv("APP_NAME", "Racecraft AI"),
        app_version=getenv("APP_VERSION", "1.0.0"),
        environment=getenv("ENVIRONMENT", "development"),
        debug=_parse_bool(getenv("DEBUG"), default=False),
        database_url=_build_database_url(),
        cors_origins=cors_origins,
        groq_api_key=groq_api_key,
        groq_model=getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    )