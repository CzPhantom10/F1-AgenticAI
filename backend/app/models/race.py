"""Race ORM model."""

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


class Race(Base):
    """Formula 1 race entity."""

    __tablename__ = "races"
    __table_args__ = (
        UniqueConstraint("season", "round_number", name="uq_races_season_round"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    race_name: Mapped[str] = mapped_column(String(150), nullable=False)
    race_date: Mapped[date] = mapped_column(Date, nullable=False)
    circuit_id: Mapped[int] = mapped_column(ForeignKey("circuits.id"), nullable=False, index=True)

    circuit = relationship("Circuit", back_populates="races")
    race_results = relationship("RaceResult", back_populates="race", cascade="all, delete-orphan")
    qualifying_results = relationship("QualifyingResult", back_populates="race", cascade="all, delete-orphan")
