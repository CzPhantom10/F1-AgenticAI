"""Qualifying result ORM model."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


class QualifyingResult(Base):
    """Single driver qualifying result for a race."""

    __tablename__ = "qualifying_results"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id", name="uq_qualifying_results_race_driver"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False, index=True)
    constructor_id: Mapped[int] = mapped_column(ForeignKey("constructors.id"), nullable=False, index=True)
    qualifying_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    q1_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    q2_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    q3_time: Mapped[float | None] = mapped_column(Float, nullable=True)

    race = relationship("Race", back_populates="qualifying_results")
    driver = relationship("Driver", back_populates="qualifying_results")
    constructor = relationship("Constructor", back_populates="qualifying_results")
