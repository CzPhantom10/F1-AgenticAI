"""Create all database tables defined by the ORM models."""

from app.database.db import Base, engine

from app.models.circuit import Circuit
from app.models.constructor import Constructor
from app.models.driver import Driver
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.memory import DriverInsight, ConstructorInsight, CircuitInsight


def init_db() -> None:
    """Create the SQLite database file and all ORM tables."""

    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database initialized")
