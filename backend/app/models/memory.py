"""Memory ORM models — pre-computed driver and constructor insight records."""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class DriverInsight(Base):
    """Pre-computed performance snapshot for a single driver."""

    __tablename__ = "driver_insights"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Career-wide aggregates (all seasons in the DB)
    total_races: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_podiums: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_points: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_finish_position: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_qualifying_position: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Last-5-races form — JSON array stored as TEXT
    # e.g. [{"race": "Bahrain GP", "finish": 2, "points": 18}, …]
    recent_form_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Per-season breakdown — JSON array stored as TEXT
    # e.g. [{"season": 2024, "races": 24, "wins": 9, "points": 437.0}, …]
    season_breakdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    rebuilt_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )

    driver = relationship("Driver", foreign_keys=[driver_id])


class ConstructorInsight(Base):
    """Pre-computed performance snapshot for a single constructor."""

    __tablename__ = "constructor_insights"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    constructor_id: Mapped[int] = mapped_column(
        ForeignKey("constructors.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Career-wide aggregates
    total_races: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_podiums: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_points: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_points_per_race: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Last-5-races form — JSON array stored as TEXT
    # e.g. [{"race": "Bahrain GP", "season": 2025, "points": 38, "podiums": 2}, …]
    recent_form_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Per-season breakdown — JSON array stored as TEXT
    # e.g. [{"season": 2024, "races": 24, "wins": 16, "podiums": 34, "points": 860.0}, …]
    season_breakdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    rebuilt_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )

    constructor = relationship("Constructor", foreign_keys=[constructor_id])


class CircuitInsight(Base):
    """Pre-computed performance snapshot for a single circuit."""

    __tablename__ = "circuit_insights"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    circuit_id: Mapped[int] = mapped_column(
        ForeignKey("circuits.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Historical winners list: list of dicts: [{"season": 2024, "driver_id": 1, "driver_name": "Max Verstappen", "constructor_name": "Red Bull"}]
    historical_winners_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Best drivers (by wins, podiums, avg finish): [{"driver_id": 1, "driver_name": "Max Verstappen", "wins": 3, "podiums": 5, "avg_finish": 2.4}]
    best_drivers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Best constructors (by wins, podiums): [{"constructor_id": 1, "constructor_name": "Red Bull", "wins": 4, "podiums": 8}]
    best_constructors_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    rebuilt_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )

    circuit = relationship("Circuit", foreign_keys=[circuit_id])


__all__ = ["ConstructorInsight", "DriverInsight", "CircuitInsight"]
