"""Standalone import script for 2024 qualifying results."""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.agents.data_agent import DataAgent
from app.core.config import get_settings
from app.database.init_db import init_db
from app.models.constructor import Constructor
from app.models.driver import Driver
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race


def main() -> None:
    """Create tables, import 2024 qualifying results, and print table counts."""

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    init_db()

    agent = DataAgent()
    qualifying_results = agent.fetch_qualifying_results(2024)

    settings = get_settings()
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})

    with Session(engine) as session:
        race_count = session.scalar(select(func.count()).select_from(Race)) or 0
        driver_count = session.scalar(select(func.count()).select_from(Driver)) or 0
        constructor_count = session.scalar(select(func.count()).select_from(Constructor)) or 0
        qualifying_count = session.scalar(select(func.count()).select_from(QualifyingResult)) or 0

    print(f"Imported qualifying rows: {len(qualifying_results)}")
    print(f"races: {race_count}")
    print(f"drivers: {driver_count}")
    print(f"constructors: {constructor_count}")
    print(f"qualifying_results: {qualifying_count}")


if __name__ == "__main__":
    main()