"""Normalize race/result string references into foreign keys for SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parents[1] / "racecraft_ai.db"


def _column_exists(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    return any(row[1] == column_name for row in cursor.execute(f"PRAGMA table_info({table_name})"))


def _index_exists(cursor: sqlite3.Cursor, index_name: str) -> bool:
    return cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).fetchone() is not None


def _create_index(cursor: sqlite3.Cursor, statement: str, index_name: str) -> None:
    if not _index_exists(cursor, index_name):
        cursor.execute(statement)


def _ensure_normalized_indexes(cursor: sqlite3.Cursor) -> None:
    _create_index(cursor, "CREATE UNIQUE INDEX ix_circuits_name ON circuits (name)", "ix_circuits_name")
    _create_index(cursor, "CREATE INDEX ix_races_id ON races (id)", "ix_races_id")
    _create_index(cursor, "CREATE INDEX ix_races_season ON races (season)", "ix_races_season")
    _create_index(cursor, "CREATE INDEX ix_races_round_number ON races (round_number)", "ix_races_round_number")
    _create_index(cursor, "CREATE INDEX ix_races_circuit_id ON races (circuit_id)", "ix_races_circuit_id")
    _create_index(cursor, "CREATE INDEX ix_race_results_id ON race_results (id)", "ix_race_results_id")
    _create_index(cursor, "CREATE INDEX ix_race_results_race_id ON race_results (race_id)", "ix_race_results_race_id")
    _create_index(cursor, "CREATE INDEX ix_race_results_driver_id ON race_results (driver_id)", "ix_race_results_driver_id")
    _create_index(
        cursor,
        "CREATE INDEX ix_race_results_constructor_id ON race_results (constructor_id)",
        "ix_race_results_constructor_id",
    )


def migrate() -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF")

        if _column_exists(cursor, "races", "circuit_id") and _column_exists(cursor, "race_results", "driver_id"):
            _ensure_normalized_indexes(cursor)
            connection.commit()
            print("Database already migrated")
            return

        race_count = cursor.execute("SELECT COUNT(*) FROM races").fetchone()[0]
        result_count = cursor.execute("SELECT COUNT(*) FROM race_results").fetchone()[0]

        cursor.execute(
            """
            INSERT OR IGNORE INTO circuits (name, country, location)
            SELECT DISTINCT circuit_name, 'Unknown', circuit_name
            FROM races
            WHERE circuit_name IS NOT NULL AND TRIM(circuit_name) != ''
            """
        )

        cursor.execute("ALTER TABLE races RENAME TO races_legacy")
        cursor.execute(
            """
            CREATE TABLE races (
                id INTEGER NOT NULL,
                season INTEGER NOT NULL,
                round_number INTEGER NOT NULL,
                race_name VARCHAR(150) NOT NULL,
                race_date DATE NOT NULL,
                circuit_id INTEGER NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT uq_races_season_round UNIQUE (season, round_number),
                FOREIGN KEY(circuit_id) REFERENCES circuits (id)
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO races (id, season, round_number, race_name, race_date, circuit_id)
            SELECT races_legacy.id,
                   races_legacy.season,
                   races_legacy.round_number,
                   races_legacy.race_name,
                   races_legacy.race_date,
                   circuits.id
            FROM races_legacy
            JOIN circuits ON circuits.name = races_legacy.circuit_name
            """
        )

        cursor.execute("ALTER TABLE race_results RENAME TO race_results_legacy")
        cursor.execute(
            """
            CREATE TABLE race_results (
                id INTEGER NOT NULL,
                race_id INTEGER NOT NULL,
                driver_id INTEGER NOT NULL,
                constructor_id INTEGER NOT NULL,
                grid_position INTEGER,
                finish_position INTEGER,
                points FLOAT,
                status VARCHAR(100) NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT uq_race_results_race_driver UNIQUE (race_id, driver_id),
                FOREIGN KEY(race_id) REFERENCES races (id) ON DELETE CASCADE,
                FOREIGN KEY(driver_id) REFERENCES drivers (id),
                FOREIGN KEY(constructor_id) REFERENCES constructors (id)
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO race_results (
                id,
                race_id,
                driver_id,
                constructor_id,
                grid_position,
                finish_position,
                points,
                status
            )
            SELECT race_results_legacy.id,
                   race_results_legacy.race_id,
                   drivers.id,
                   constructors.id,
                   race_results_legacy.grid_position,
                   race_results_legacy.finish_position,
                   race_results_legacy.points,
                   race_results_legacy.status
            FROM race_results_legacy
            JOIN drivers
              ON LOWER(TRIM(drivers.first_name || ' ' || drivers.last_name))
               = LOWER(TRIM(race_results_legacy.driver_name))
            JOIN constructors
              ON constructors.name = race_results_legacy.constructor_name
            """
        )

        migrated_race_count = cursor.execute("SELECT COUNT(*) FROM races").fetchone()[0]
        migrated_result_count = cursor.execute("SELECT COUNT(*) FROM race_results").fetchone()[0]

        if migrated_race_count != race_count:
            raise RuntimeError(f"Race migration lost rows: {migrated_race_count} != {race_count}")
        if migrated_result_count != result_count:
            raise RuntimeError(f"Race result migration lost rows: {migrated_result_count} != {result_count}")

        cursor.execute("DROP TABLE race_results_legacy")
        cursor.execute("DROP TABLE races_legacy")

        _ensure_normalized_indexes(cursor)

        cursor.execute("PRAGMA foreign_keys = ON")
        connection.commit()

        print(
            "Migration complete: "
            f"races={migrated_race_count}, "
            f"race_results={migrated_result_count}, "
            f"circuits={cursor.execute('SELECT COUNT(*) FROM circuits').fetchone()[0]}"
        )


if __name__ == "__main__":
    migrate()
