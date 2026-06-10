"""Constructor ORM model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


class Constructor(Base):
    """Formula 1 constructor entity."""

    __tablename__ = "constructors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    nationality: Mapped[str] = mapped_column(String(100), nullable=False)

    race_results = relationship("RaceResult", back_populates="constructor")
    qualifying_results = relationship("QualifyingResult", back_populates="constructor")
