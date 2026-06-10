"""Smoke test for inserting and retrieving a sample driver row."""

from __future__ import annotations

from sqlalchemy import delete, select

from app.database.db import SessionLocal
from app.database.init_db import init_db
from app.models.driver import Driver


def run_driver_roundtrip_test() -> Driver:
    """Insert a sample driver record and fetch it back from SQLite."""

    init_db()

    sample_code = "TST01"

    with SessionLocal() as session:
        session.execute(delete(Driver).where(Driver.driver_code == sample_code))
        session.add(
            Driver(
                driver_code=sample_code,
                first_name="Test",
                last_name="Driver",
                nationality="Testland",
            )
        )
        session.commit()

        statement = select(Driver).where(Driver.driver_code == sample_code)
        retrieved_driver = session.scalars(statement).one()

        print(
            f"Retrieved driver: {retrieved_driver.driver_code} "
            f"{retrieved_driver.first_name} {retrieved_driver.last_name}"
        )

        return retrieved_driver


if __name__ == "__main__":
    run_driver_roundtrip_test()