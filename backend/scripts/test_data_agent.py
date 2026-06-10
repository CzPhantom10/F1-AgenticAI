"""Standalone smoke test for the Racecraft AI DataAgent."""

from __future__ import annotations

import logging

from app.agents.data_agent import DataAgent
from app.database.init_db import init_db


def main() -> None:
    """Create tables and populate the 2024 season race results using FastF1."""

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    init_db()

    agent = DataAgent()
    season_results = agent.fetch_race_results(2024)

    print(f"Stored {len(season_results)} race results for 2024")


if __name__ == "__main__":
    main()