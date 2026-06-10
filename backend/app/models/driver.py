"""Driver ORM model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


class Driver(Base):
	"""Formula 1 driver entity."""

	__tablename__ = "drivers"

	id: Mapped[int] = mapped_column(primary_key=True, index=True)
	driver_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
	first_name: Mapped[str] = mapped_column(String(100), nullable=False)
	last_name: Mapped[str] = mapped_column(String(100), nullable=False)
	nationality: Mapped[str] = mapped_column(String(100), nullable=False)
	race_results = relationship("RaceResult", back_populates="driver")
	qualifying_results = relationship("QualifyingResult", back_populates="driver")


__all__ = ["Driver"]
