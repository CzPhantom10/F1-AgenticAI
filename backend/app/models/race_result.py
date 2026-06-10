"""Race result ORM model."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


class RaceResult(Base):
    """Single driver result for a race."""

    __tablename__ = "race_results"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id", name="uq_race_results_race_driver"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False, index=True)
    constructor_id: Mapped[int] = mapped_column(ForeignKey("constructors.id"), nullable=False, index=True)
    grid_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finish_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(100), nullable=False)

    race = relationship("Race", back_populates="race_results")
    driver = relationship("Driver", back_populates="race_results")
    constructor = relationship("Constructor", back_populates="race_results")
